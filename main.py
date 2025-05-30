import sys
import os
import traceback
import logging
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QPushButton, QFileDialog,
                             QLineEdit, QCheckBox, QProgressBar, QSpinBox,
                             QMessageBox, QGroupBox, QRadioButton, QStackedWidget,
                             QSlider, QDialog, QFrame, QStyle)
from PyQt5.QtGui import QFont, QIcon, QPixmap
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QSize, QMutex, QWaitCondition

import threading
import time

from pdf_recovery import PDFPasswordRecovery
from password_generator import PasswordGenerator

# Try to import psutil for memory monitoring
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    logging.warning("psutil package not found. Memory monitoring will be disabled. Install with 'pip install psutil'.")

# Set up logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('PDFPasswordRecovery')

class PasswordGenerationThread(QThread):
    """Thread for generating passwords in the background"""
    progress_update = pyqtSignal(int)
    password_list_ready = pyqtSignal(list)
    generation_failed = pyqtSignal(str)
    current_pattern_update = pyqtSignal(str)  # Signal for current pattern being generated
    memory_warning = pyqtSignal(float)  # Signal for memory usage warnings
    processing_large_list = pyqtSignal(int)  # Signal for processing large list after generation
    
    def __init__(self, min_length, max_length, char_options, no_limit, memory_limit_mb=1000):
        super().__init__()
        self.min_length = min_length
        self.max_length = max_length
        self.char_options = char_options
        self.no_limit = no_limit
        self.memory_limit_mb = memory_limit_mb
        self.cancelled = False
        self.mutex = QMutex()  # Thread safety
        
    def run(self):
        try:
            # Create generator
            generator = PasswordGenerator(
                min_length=self.min_length,
                max_length=self.max_length,
                use_lowercase=self.char_options['lowercase'],
                use_uppercase=self.char_options['uppercase'],
                use_digits=self.char_options['digits'],
                use_special=self.char_options['special'],
                no_limit=self.no_limit
            )
            
            # Get password list with progress reporting
            password_list = []
            total_estimate = generator.estimate_count()
            
            # Report initial progress
            self.progress_update.emit(0)
            
            # Set up callback for progress updates
            def progress_callback(count, total):
                # Check if cancelled
                if self.check_cancelled():
                    return False  # Signal to stop generation
                    
                # Check memory usage occasionally
                if count % 10000 == 0:
                    self.check_memory_usage()
                    
                # Update UI
                progress = min(int((count / total) * 100), 99)  # Max 99% until complete
                self.progress_update.emit(progress)
                
                # Keep the UI responsive by processing events
                QApplication.processEvents()
                return True  # Continue generation
            
            # Set up pattern callback for updating UI
            def pattern_callback(pattern):
                # Check if cancelled
                if self.check_cancelled():
                    return False  # Signal to stop generation
                    
                self.current_pattern_update.emit(pattern)
                return True  # Continue generation
                
            # Generate passwords with progress reporting
            password_list = generator.generate_passwords(progress_callback, pattern_callback)
            
            # Check if we were cancelled
            if self.check_cancelled():
                logger.info("Password generation cancelled")
                return
            
            # For large lists, inform UI we're processing
            if len(password_list) > 100000:
                self.progress_update.emit(99)  # Keep at 99% while processing
                self.current_pattern_update.emit(f"Processing {len(password_list):,} passwords")
                self.processing_large_list.emit(len(password_list))
                
                # Process in chunks and allow UI to breathe
                for _ in range(10):  # Arbitrary number of breaths
                    QApplication.processEvents()
                    time.sleep(0.05)  # Short sleep to ensure UI updates
            
            # Emit final result
            self.progress_update.emit(100)
            self.password_list_ready.emit(password_list)
            
        except Exception as e:
            logger.error(f"Password generation failed: {str(e)}")
            self.generation_failed.emit(str(e))
            
    def cancel(self):
        """Cancel password generation"""
        self.mutex.lock()
        self.cancelled = True
        self.mutex.unlock()
        
    def check_cancelled(self):
        """Check if generation has been cancelled, thread-safe"""
        self.mutex.lock()
        result = self.cancelled
        self.mutex.unlock()
        return result
        
    def check_memory_usage(self):
        """Check current memory usage and warn/cancel if needed"""
        if not PSUTIL_AVAILABLE:
            return
            
        try:
            process = psutil.Process()
            memory_mb = process.memory_info().rss / (1024 * 1024)  # MB
            
            # Warn at 80% of limit
            if memory_mb > (self.memory_limit_mb * 0.8):
                self.memory_warning.emit(memory_mb)
                
            # Cancel at 95% of limit to prevent crashes
            if memory_mb > (self.memory_limit_mb * 0.95):
                logger.warning(f"Memory limit approaching during generation: {memory_mb:.1f} MB")
                self.cancel()
                
        except Exception as e:
            logger.error(f"Error checking memory during generation: {e}")


class PasswordRecoveryThread(QThread):
    progress_update = pyqtSignal(int)
    password_found = pyqtSignal(str)
    password_not_found = pyqtSignal()
    memory_warning = pyqtSignal(float)  # Signal for memory usage warnings
    current_password_update = pyqtSignal(str)  # Signal for current password being checked
    
    def __init__(self, pdf_path, password_list, memory_limit_mb=1000):
        super().__init__()
        self.pdf_path = pdf_path
        self.password_list = password_list
        self.memory_limit_mb = memory_limit_mb
        self.paused = False
        self.cancelled = False
        self.mutex = QMutex()  # For thread-safe access to pause/cancel flags
        self.resume_condition = QWaitCondition()  # For pausing/resuming
        
        # Track the last position to support resume
        self.current_position = 0
        
    def run(self):
        recovery = PDFPasswordRecovery(self.pdf_path)
        total = len(self.password_list)
        
        # Process in batches to avoid UI freezing and to check pause/cancel between batches
        batch_size = 100  # Check 100 passwords before checking for pause/cancel
        
        # Start from the last position (useful for resume)
        i = self.current_position
        
        while i < total:
            # Check if we should stop
            if self.check_cancelled():
                return
                
            # Check if we should pause
            self.check_paused()
            
            # Process a batch of passwords
            end_batch = min(i + batch_size, total)
            for j in range(i, end_batch):
                password = self.password_list[j]
                
                # Update UI with current password being checked
                if j % 10 == 0:  # Update every 10 passwords to avoid UI flooding
                    self.current_password_update.emit(password)
                
                # Process one password
                if recovery.try_password(password):
                    self.password_found.emit(password)
                    return
                    
                # Update our current position
                self.current_position = j + 1
                
            # Update progress after each batch
            progress = int((end_batch) / total * 100)
            self.progress_update.emit(progress)
            
            # Check memory usage occasionally
            if i % 1000 == 0:
                self.check_memory_usage()
                
            # Move to next batch
            i = end_batch
            
            # Give the UI a chance to process events
            QApplication.processEvents()
            
        # If we got here, no password was found
        self.password_not_found.emit()
        
    def pause(self):
        """Pause the password recovery process"""
        self.mutex.lock()
        self.paused = True
        self.mutex.unlock()
        
    def resume(self):
        """Resume the password recovery process"""
        self.mutex.lock()
        self.paused = False
        self.resume_condition.wakeAll()  # Wake up the thread
        self.mutex.unlock()
        
    def cancel(self):
        """Cancel the password recovery process"""
        self.mutex.lock()
        self.cancelled = True
        self.paused = False  # Make sure to wake up the thread if it's paused
        self.resume_condition.wakeAll()
        self.mutex.unlock()
        
    def check_cancelled(self):
        """Check if the thread should be cancelled, thread-safe"""
        self.mutex.lock()
        result = self.cancelled
        self.mutex.unlock()
        return result
        
    def check_paused(self):
        """Check if the thread should be paused, thread-safe"""
        self.mutex.lock()
        if self.paused:
            # Wait until resumed
            self.resume_condition.wait(self.mutex)
        self.mutex.unlock()
        
    def check_memory_usage(self):
        """Check if memory usage is approaching the limit"""
        try:
            import psutil
            process = psutil.Process()
            memory_mb = process.memory_info().rss / (1024 * 1024)  # Convert to MB
            
            # If memory usage is over 80% of the limit, emit warning
            if memory_mb > (self.memory_limit_mb * 0.8):
                self.memory_warning.emit(memory_mb)
                
            # If memory usage exceeds the limit, cancel the operation
            if memory_mb > self.memory_limit_mb:
                logger.warning(f"Memory limit exceeded: {memory_mb} MB used, limit is {self.memory_limit_mb} MB")
                self.cancel()
                
        except ImportError:
            logger.warning("psutil not available, memory monitoring disabled")
        except Exception as e:
            logger.error(f"Error checking memory usage: {str(e)}")


class PDFPasswordRecoveryApp(QMainWindow):
    def __init__(self):
        super().__init__()
        logger.info("Initializing PDF Password Recovery App")
        self.init_ui()
        
    def init_ui(self):
        self.setWindowTitle("Kanna PDF Password Recovery")
        self.setMinimumSize(600, 500)
        
        # Main widget and layout
        main_widget = QWidget()
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)
        
        # Header
        header_label = QLabel("Kanna PDF Password Recovery")
        header_label.setFont(QFont("Arial", 18, QFont.Bold))
        header_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(header_label)
        
        # Description
        desc_label = QLabel("Recover forgotten passwords from your PDF documents")
        desc_label.setFont(QFont("Arial", 10))
        desc_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(desc_label)
        
        # Steps container (stacked widget)
        self.steps_widget = QStackedWidget()
        main_layout.addWidget(self.steps_widget)
        
        # Create step pages
        self.create_step1_ui()  # Select PDF file
        self.create_step2_ui()  # Password generation options
        self.create_step3_ui()  # Password recovery process
        
        # Set the initial step
        self.steps_widget.setCurrentIndex(0)
        
        # Footer
        footer_layout = QHBoxLayout()
        self.prev_button = QPushButton("Previous")
        self.prev_button.setEnabled(False)
        self.prev_button.clicked.connect(self.go_to_previous_step)
        
        self.next_button = QPushButton("Next")
        self.next_button.clicked.connect(self.go_to_next_step)
        
        footer_layout.addWidget(self.prev_button)
        footer_layout.addStretch()
        footer_layout.addWidget(self.next_button)
        main_layout.addLayout(footer_layout)
        
        # Variables
        self.pdf_path = None
        self.password_list = []
        self.recovery_thread = None
        self.is_recovery_paused = False
        
        # Default the disclaimer checkbox to unchecked
        self.disclaimer_checkbox.setEnabled(False)
        
        # Set central widget
        self.setCentralWidget(main_widget)
        
    def create_step1_ui(self):
        # Step 1: Select PDF file
        step1_widget = QWidget()
        step1_layout = QVBoxLayout(step1_widget)
        
        # Step title
        step_title = QLabel("Step 1: Select PDF File")
        step_title.setFont(QFont("Arial", 14, QFont.Bold))
        step1_layout.addWidget(step_title)
        
        # PDF selection
        pdf_group = QGroupBox("PDF File Selection")
        pdf_layout = QVBoxLayout()
        
        file_layout = QHBoxLayout()
        self.pdf_path_input = QLineEdit()
        self.pdf_path_input.setPlaceholderText("No file selected")
        self.pdf_path_input.setReadOnly(True)
        
        browse_button = QPushButton("Browse")
        browse_button.clicked.connect(self.browse_pdf)
        
        file_layout.addWidget(self.pdf_path_input)
        file_layout.addWidget(browse_button)
        
        pdf_layout.addLayout(file_layout)
        pdf_group.setLayout(pdf_layout)
        step1_layout.addWidget(pdf_group)
        
        # Add spacer at the bottom
        step1_layout.addStretch()
        
        self.steps_widget.addWidget(step1_widget)
        
    def create_step2_ui(self):
        # Step 2: Password generation options
        step2_widget = QWidget()
        step2_layout = QVBoxLayout(step2_widget)
        
        # Step title
        step_title = QLabel("Step 2: Configure Password List")
        step_title.setFont(QFont("Arial", 14, QFont.Bold))
        step2_layout.addWidget(step_title)
        
        # Password length group
        length_group = QGroupBox("Password Length")
        length_layout = QHBoxLayout()
        
        length_layout.addWidget(QLabel("Min Length:"))
        self.min_length_spin = QSpinBox()
        self.min_length_spin.setMinimum(1)
        self.min_length_spin.setMaximum(10)
        self.min_length_spin.setValue(4)
        length_layout.addWidget(self.min_length_spin)
        
        length_layout.addWidget(QLabel("Max Length:"))
        self.max_length_spin = QSpinBox()
        self.max_length_spin.setMinimum(1)
        self.max_length_spin.setMaximum(12)
        self.max_length_spin.setValue(6)
        length_layout.addWidget(self.max_length_spin)
        
        length_group.setLayout(length_layout)
        step2_layout.addWidget(length_group)
        
        # Character options group
        char_group = QGroupBox("Character Options")
        char_layout = QVBoxLayout()
        
        self.use_lowercase = QCheckBox("Include lowercase letters (a-z)")
        self.use_lowercase.setChecked(True)
        
        self.use_uppercase = QCheckBox("Include uppercase letters (A-Z)")
        
        self.use_digits = QCheckBox("Include digits (0-9)")
        self.use_digits.setChecked(True)
        
        self.use_special = QCheckBox("Include special characters (!@#$%^&*)")
        
        char_layout.addWidget(self.use_lowercase)
        char_layout.addWidget(self.use_uppercase)
        char_layout.addWidget(self.use_digits)
        char_layout.addWidget(self.use_special)
        
        char_group.setLayout(char_layout)
        step2_layout.addWidget(char_group)
        
        # Password limit group
        limit_group = QGroupBox("Password Limits")
        limit_layout = QVBoxLayout()
        
        # Create a checkbox for unlimited passwords
        self.no_limit_checkbox = QCheckBox("I want to generate all possible passwords")
        limit_layout.addWidget(self.no_limit_checkbox)
        
        # Add a warning disclaimer checkbox
        self.disclaimer_checkbox = QCheckBox("I understand that generating large password lists (>1,000,000) may crash low-end PCs")
        self.disclaimer_checkbox.setStyleSheet("color: #FF0000; font-weight: bold;")
        limit_layout.addWidget(self.disclaimer_checkbox)
        
        # Add description about memory usage
        memory_warning = QLabel("Warning: Removing the password limit can cause the application to run out of memory depending on your settings and hardware.")
        memory_warning.setStyleSheet("color: #FF5500;")
        memory_warning.setWordWrap(True)
        limit_layout.addWidget(memory_warning)
        
        # Memory limit settings
        memory_group = QHBoxLayout()
        memory_group.addWidget(QLabel("Memory Limit (MB):"))
        
        self.memory_limit_slider = QSpinBox()
        self.memory_limit_slider.setMinimum(500)
        self.memory_limit_slider.setMaximum(16000)  # Up to 16GB
        
        # Set default memory limit to 50% of system memory or 1GB, whichever is higher
        default_memory = 1000  # Default to 1GB
        if PSUTIL_AVAILABLE:
            try:
                system_memory_mb = psutil.virtual_memory().total / (1024 * 1024)
                default_memory = max(1000, int(system_memory_mb * 0.5))
                default_memory = min(default_memory, 16000)  # Cap at 16GB
            except Exception as e:
                logger.error(f"Error getting system memory: {e}")
        
        self.memory_limit_slider.setValue(default_memory)
        self.memory_limit_slider.setSingleStep(100)
        memory_group.addWidget(self.memory_limit_slider)
        
        limit_layout.addLayout(memory_group)
        
        if not PSUTIL_AVAILABLE:
            psutil_warning = QLabel("Note: Install 'psutil' package for memory monitoring")
            psutil_warning.setStyleSheet("font-style: italic;")
            limit_layout.addWidget(psutil_warning)
        
        # Connect checkbox signals
        self.no_limit_checkbox.toggled.connect(self.toggle_disclaimer)
        
        limit_group.setLayout(limit_layout)
        step2_layout.addWidget(limit_group)
        
        # Password count estimate
        estimate_layout = QHBoxLayout()
        estimate_layout.addWidget(QLabel("Estimated password list size:"))
        self.password_count_label = QLabel("0")
        self.password_count_label.setFont(QFont("Arial", 10, QFont.Bold))
        estimate_layout.addWidget(self.password_count_label)
        step2_layout.addLayout(estimate_layout)
        
        # Update estimate button
        update_button = QPushButton("Calculate Estimate")
        update_button.clicked.connect(self.update_password_estimate)
        step2_layout.addWidget(update_button)
        
        # Add spacer
        step2_layout.addStretch()
        
        self.steps_widget.addWidget(step2_widget)
        
    def create_step3_ui(self):
        # Step 3: Password recovery process
        step3_widget = QWidget()
        step3_layout = QVBoxLayout(step3_widget)
        
        # Step title
        step_title = QLabel("Step 3: Recover Password")
        step_title.setFont(QFont("Arial", 14, QFont.Bold))
        step3_layout.addWidget(step_title)
        
        # Status info
        status_group = QGroupBox("Recovery Status")
        status_layout = QVBoxLayout()
        
        self.pdf_info_label = QLabel("PDF: Not selected")
        self.password_info_label = QLabel("Password List: Not generated")
        self.memory_usage_label = QLabel("Memory Usage: 0 MB")
        self.current_password_label = QLabel("Current Password: -")
        status_layout.addWidget(self.pdf_info_label)
        status_layout.addWidget(self.password_info_label)
        status_layout.addWidget(self.memory_usage_label)
        status_layout.addWidget(self.current_password_label)
        
        status_group.setLayout(status_layout)
        step3_layout.addWidget(status_group)
        
        # Progress
        progress_layout = QVBoxLayout()
        progress_label = QLabel("Password Recovery Progress:")
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        
        progress_layout.addWidget(progress_label)
        progress_layout.addWidget(self.progress_bar)
        step3_layout.addLayout(progress_layout)
        
        # Result display
        self.result_label = QLabel("")
        self.result_label.setFont(QFont("Arial", 12, QFont.Bold))
        self.result_label.setAlignment(Qt.AlignCenter)
        step3_layout.addWidget(self.result_label)
        
        # Control buttons layout
        control_layout = QHBoxLayout()
        
        # Start button
        self.start_button = QPushButton("Start Recovery")
        self.start_button.clicked.connect(self.start_password_recovery)
        control_layout.addWidget(self.start_button)
        
        # Pause button
        self.pause_button = QPushButton("Pause")
        self.pause_button.clicked.connect(self.toggle_pause_recovery)
        self.pause_button.setEnabled(False)
        control_layout.addWidget(self.pause_button)
        
        # Cancel button
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.cancel_recovery)
        self.cancel_button.setEnabled(False)
        control_layout.addWidget(self.cancel_button)
        
        step3_layout.addLayout(control_layout)
        
        # Add spacer
        step3_layout.addStretch()
        
        self.steps_widget.addWidget(step3_widget)
    
    def browse_pdf(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select PDF File", "", "PDF Files (*.pdf)")
        if file_path:
            self.pdf_path = file_path
            self.pdf_path_input.setText(file_path)
            
            # Validate the PDF
            recovery = PDFPasswordRecovery(file_path)
            is_valid, message = recovery.validate_pdf()
            
            if not is_valid:
                QMessageBox.warning(self, "Invalid PDF", message)
                self.pdf_path = None
                self.pdf_path_input.setText("")
            else:
                logger.info(f"Selected valid PDF: {file_path}")
    
    def toggle_disclaimer(self, checked):
        """Enable or disable the disclaimer checkbox based on the no-limit checkbox state"""
        self.disclaimer_checkbox.setEnabled(checked)
        if not checked:
            self.disclaimer_checkbox.setChecked(False)
    
    def update_password_estimate(self):
        min_length = self.min_length_spin.value()
        max_length = self.max_length_spin.value()
        
        # Make sure min_length is not greater than max_length
        if min_length > max_length:
            QMessageBox.warning(self, "Invalid Length", "Minimum length cannot be greater than maximum length.")
            self.min_length_spin.setValue(max_length)
            min_length = max_length
            
        char_options = {
            'lowercase': self.use_lowercase.isChecked(),
            'uppercase': self.use_uppercase.isChecked(),
            'digits': self.use_digits.isChecked(),
            'special': self.use_special.isChecked()
        }
        
        # Count number of selected character types
        char_count = 0
        if char_options['lowercase']:
            char_count += 26  # a-z
        if char_options['uppercase']:
            char_count += 26  # A-Z
        if char_options['digits']:
            char_count += 10  # 0-9
        if char_options['special']:
            char_count += 8   # Special chars count
            
        # Make sure at least one character type is selected
        if char_count == 0:
            QMessageBox.warning(self, "Invalid Options", "Please select at least one character type.")
            self.use_lowercase.setChecked(True)
            char_count = 26
            
        # Calculate estimate
        estimate = 0
        for length in range(min_length, max_length + 1):
            estimate += char_count ** length
            
        # Check if we're in no-limit mode
        no_limit = self.no_limit_checkbox.isChecked() and self.disclaimer_checkbox.isChecked()
        
        # Apply limit if not in no-limit mode
        if not no_limit:
            estimate = min(estimate, 1000000)  # Default limit
            
        # Format the number
        if estimate < 1000:
            estimate_text = str(estimate)
        elif estimate < 1000000:
            estimate_text = f"{estimate/1000:.1f}K"
        else:
            estimate_text = f"{estimate/1000000:.1f}M"
            
        self.password_count_label.setText(estimate_text)
    
    def go_to_next_step(self):
        current_index = self.steps_widget.currentIndex()
        
        # Validation for each step
        if current_index == 0:  # Step 1: Validate PDF selection
            if not self.pdf_path:
                QMessageBox.warning(self, "Error", "Please select a PDF file first.")
                return
                
            # Double-check PDF file is valid
            try:
                recovery = PDFPasswordRecovery(self.pdf_path)
                is_valid, message = recovery.validate_pdf()
                
                if not is_valid:
                    QMessageBox.warning(self, "Invalid PDF", message)
                    return
                    
                logger.info(f"Moving to step 2 with PDF: {self.pdf_path}")
            except Exception as e:
                logger.error(f"Error validating PDF: {str(e)}")
                QMessageBox.warning(self, "Error", f"Could not validate PDF: {str(e)}")
                return
                
        elif current_index == 1:  # Step 2: Validate password options
            min_length = self.min_length_spin.value()
            max_length = self.max_length_spin.value()
            
            if min_length > max_length:
                QMessageBox.warning(self, "Error", "Minimum length cannot be greater than maximum length.")
                return
                
            char_options = {
                'lowercase': self.use_lowercase.isChecked(),
                'uppercase': self.use_uppercase.isChecked(),
                'digits': self.use_digits.isChecked(),
                'special': self.use_special.isChecked()
            }
            
            if not any(char_options.values()):
                QMessageBox.warning(self, "Error", "Please select at least one character type.")
                return
            
            # Get no-limit setting
            no_limit = self.no_limit_checkbox.isChecked()
            
            # Verify that disclaimer is acknowledged if no-limit is checked
            if no_limit and not self.disclaimer_checkbox.isChecked():
                QMessageBox.warning(
                    self, 
                    "Disclaimer Required", 
                    "You must acknowledge the warning about large password lists before proceeding."
                )
                return
                
            # Extra confirmation for no-limit mode
            if no_limit:
                confirm = QMessageBox.warning(
                    self, 
                    "No Password Limit", 
                    "WARNING: You've chosen to remove the password limit. This may cause the application to crash or become unresponsive if generating a very large number of passwords.\n\nAre you sure you want to continue?",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No
                )
                
                if confirm == QMessageBox.No:
                    return
                
            # Show password generation dialog with progress bar
            self.show_password_generation_dialog(min_length, max_length, char_options, no_limit)
            return  # Don't advance step yet - we'll do that after password generation
            
        # Move to next step if validation passes
        if current_index < self.steps_widget.count() - 1:
            self.steps_widget.setCurrentIndex(current_index + 1)
            
        # Update button states
        self.update_button_states()
    
    def show_password_generation_dialog(self, min_length, max_length, char_options, no_limit):
        """Show a dialog with progress bar while generating passwords"""
        # Create a custom dialog instead of QMessageBox for better layout control
        self.generation_dialog = QDialog(self)
        self.generation_dialog.setWindowTitle("Generating Passwords")
        self.generation_dialog.setMinimumWidth(400)
        
        # Setup main layout
        main_layout = QVBoxLayout(self.generation_dialog)
        
        # Add header with icon and text
        header_layout = QHBoxLayout()
        icon_label = QLabel()
        icon = self.style().standardIcon(QStyle.SP_MessageBoxInformation)
        icon_label.setPixmap(icon.pixmap(32, 32))
        header_layout.addWidget(icon_label)
        
        text_label = QLabel("Generating password list...\nThis may take a while for large lists.")
        header_layout.addWidget(text_label, 1)
        main_layout.addLayout(header_layout)
        
        # Add current pattern label with fixed height and word wrap
        self.generation_pattern_label = QLabel("Currently generating: ")
        self.generation_pattern_label.setWordWrap(True)
        self.generation_pattern_label.setMinimumHeight(50)  # Ensure enough height for multiple lines
        self.generation_pattern_label.setFrameStyle(QFrame.Panel | QFrame.Sunken)
        self.generation_pattern_label.setLineWidth(1)
        self.generation_pattern_label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.generation_pattern_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        main_layout.addWidget(self.generation_pattern_label)
        
        # Add progress bar
        self.generation_progress = QProgressBar()
        self.generation_progress.setRange(0, 100)
        self.generation_progress.setValue(0)
        self.generation_progress.setTextVisible(True)
        main_layout.addWidget(self.generation_progress)
        
        # Add memory usage label
        self.generation_memory_label = QLabel("Memory usage: Monitoring...")
        main_layout.addWidget(self.generation_memory_label)
        
        # Add cancel button
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        self.cancel_generation_button = QPushButton("Cancel Generation")
        self.cancel_generation_button.clicked.connect(self.cancel_generation)
        button_layout.addWidget(self.cancel_generation_button)
        main_layout.addLayout(button_layout)
        
        # Make dialog non-modal so UI remains responsive
        self.generation_dialog.setModal(False)
        self.generation_dialog.show()
        
        # Get memory limit
        memory_limit = self.memory_limit_slider.value()
        
        # Start password generation thread
        self.generation_thread = PasswordGenerationThread(
            min_length=min_length,
            max_length=max_length,
            char_options=char_options,
            no_limit=no_limit,
            memory_limit_mb=memory_limit
        )
        
        # Connect signals
        self.generation_thread.progress_update.connect(self.update_generation_progress)
        self.generation_thread.password_list_ready.connect(self.on_password_generation_complete)
        self.generation_thread.generation_failed.connect(self.on_password_generation_failed)
        self.generation_thread.current_pattern_update.connect(self.update_generation_pattern)
        self.generation_thread.memory_warning.connect(self.on_generation_memory_warning)
        self.generation_thread.processing_large_list.connect(self.on_processing_large_list)
        
        # Start the thread
        logger.info(f"Starting password generation with min_length={min_length}, max_length={max_length}, no_limit={no_limit}")
        self.generation_thread.start()
    
    def update_generation_progress(self, value):
        """Update the password generation progress bar"""
        if hasattr(self, 'generation_progress'):
            self.generation_progress.setValue(value)
    
    def update_generation_pattern(self, pattern):
        """Update the password pattern being generated"""
        if hasattr(self, 'generation_pattern_label'):
            # Truncate very long patterns to avoid UI issues
            display_pattern = pattern
            if len(pattern) > 30:
                display_pattern = pattern[:27] + '...'
            self.generation_pattern_label.setText(f"Currently generating: {display_pattern}")
    
    def on_password_generation_complete(self, password_list):
        """Handle completion of password generation"""
        self.password_list = password_list
        logger.info(f"Password generation complete: {len(self.password_list)} passwords generated")
        
        # Close the progress dialog
        if hasattr(self, 'generation_dialog'):
            self.generation_dialog.accept()
            
        # Update the display in step 3
        self.pdf_info_label.setText(f"PDF: {os.path.basename(self.pdf_path)}")
        self.password_info_label.setText(f"Password List: {len(self.password_list)} passwords")
        
        # Move to the next step
        current_index = self.steps_widget.currentIndex()
        if current_index < self.steps_widget.count() - 1:
            self.steps_widget.setCurrentIndex(current_index + 1)
            
        # Update button states
        self.update_button_states()
    
    def on_password_generation_failed(self, error_message):
        """Handle failure in password generation"""
        # Close the progress dialog
        if hasattr(self, 'generation_dialog'):
            self.generation_dialog.reject()
            
        # Show error message
        QMessageBox.critical(self, "Password Generation Failed", 
                          f"Failed to generate passwords: {error_message}")
                          
        # Clear any partial password list
        self.password_list = []
            
        # Don't advance to the next step since generation failed
    
    def cancel_generation(self):
        """Cancel the password generation process"""
        if hasattr(self, 'generation_thread') and self.generation_thread.isRunning():
            # Confirm cancellation
            confirm = QMessageBox.question(
                self,
                "Cancel Generation",
                "Are you sure you want to cancel password generation?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            
            if confirm == QMessageBox.Yes:
                logger.info("Password generation cancelled by user")
                self.generation_thread.cancel()
                self.generation_dialog.reject()
    
    def on_generation_memory_warning(self, memory_mb):
        """Handle memory warning during generation"""
        if hasattr(self, 'generation_memory_label'):
            self.generation_memory_label.setText(f"Memory usage: {memory_mb:.1f} MB (High)")
            self.generation_memory_label.setStyleSheet("color: red; font-weight: bold;")
            
    def on_processing_large_list(self, count):
        """Handle notification that we're processing a large password list"""
        if hasattr(self, 'generation_pattern_label'):
            self.generation_pattern_label.setText(f"Processing {count:,} passwords... Please wait")
            self.generation_pattern_label.setStyleSheet("font-weight: bold; color: blue;")
            
        # Update progress bar to show activity
        if hasattr(self, 'generation_progress'):
            self.generation_progress.setFormat("Finalizing... %p%")
            
        # Force UI to update
        QApplication.processEvents()
            
    def go_to_previous_step(self):
        current_index = self.steps_widget.currentIndex()
        
        if current_index > 0:
            self.steps_widget.setCurrentIndex(current_index - 1)
            
        self.update_button_states()
    
    def update_button_states(self):
        current_index = self.steps_widget.currentIndex()
        
        # Previous button
        self.prev_button.setEnabled(current_index > 0)
        
        # Next button
        is_last_step = current_index == self.steps_widget.count() - 1
        self.next_button.setVisible(not is_last_step)
        
    def start_password_recovery(self):
        if not self.pdf_path or not self.password_list:
            QMessageBox.warning(self, "Error", "Missing required information. Please complete all previous steps.")
            return
        
        # Check if file still exists and is accessible
        if not os.path.exists(self.pdf_path):
            QMessageBox.warning(self, "Error", "The selected PDF file no longer exists.")
            return
            
        # Validate that the password list is not empty
        if len(self.password_list) == 0:
            QMessageBox.warning(self, "Error", "The password list is empty. Please go back and select different options.")
            return
            
        logger.info(f"Starting password recovery with {len(self.password_list)} passwords")
        
        # Get memory limit
        memory_limit = self.memory_limit_slider.value()
            
        # Update UI buttons
        self.start_button.setEnabled(False)
        self.pause_button.setEnabled(True)
        self.pause_button.setText("Pause")
        self.cancel_button.setEnabled(True)
        self.result_label.setText("Searching for password...")
        
        # Reset progress
        self.progress_bar.setValue(0)
        self.memory_usage_label.setText("Memory Usage: Monitoring...")
        
        # Start recovery in a separate thread
        self.recovery_thread = PasswordRecoveryThread(
            self.pdf_path, 
            self.password_list, 
            memory_limit_mb=memory_limit
        )
        
        # Connect signals
        self.recovery_thread.progress_update.connect(self.update_progress)
        self.recovery_thread.password_found.connect(self.on_password_found)
        self.recovery_thread.password_not_found.connect(self.on_password_not_found)
        self.recovery_thread.memory_warning.connect(self.on_memory_warning)
        self.recovery_thread.current_password_update.connect(self.update_current_password)
        
        # Start the thread
        self.is_recovery_paused = False
        self.recovery_thread.start()
        
    def update_progress(self, value):
        self.progress_bar.setValue(value)
        
    def update_current_password(self, password):
        """Update the displayed currently checking password"""
        self.current_password_label.setText(f"Currently Checking: {password}")
        
    def on_password_found(self, password):
        self.progress_bar.setValue(100)
        self.result_label.setText(f"Password Found: {password}")
        self.start_button.setEnabled(True)
        self.start_button.setText("New Recovery")
        self.pause_button.setEnabled(False)
        self.cancel_button.setEnabled(False)
        QMessageBox.information(self, "Success", f"Password found: {password}")
        
    def on_password_not_found(self):
        self.progress_bar.setValue(100)
        self.result_label.setText("No password found. Try different options.")
        self.start_button.setEnabled(True)
        self.start_button.setText("Try Again")
        self.pause_button.setEnabled(False)
        self.cancel_button.setEnabled(False)
        QMessageBox.warning(self, "Not Found", "No password found with current options.")
        
    def toggle_pause_recovery(self):
        if not hasattr(self, 'recovery_thread') or not self.recovery_thread.isRunning():
            return
            
        if not hasattr(self, 'is_recovery_paused'):
            self.is_recovery_paused = False
            
        if self.is_recovery_paused:
            # Resume
            self.recovery_thread.resume()
            self.pause_button.setText("Pause")
            self.result_label.setText("Searching for password...")
            self.is_recovery_paused = False
            logger.info("Password recovery resumed")
        else:
            # Pause
            self.recovery_thread.pause()
            self.pause_button.setText("Resume")
            self.result_label.setText("Recovery paused. Click Resume to continue.")
            self.is_recovery_paused = True
            logger.info("Password recovery paused")
            
    def cancel_recovery(self):
        if not hasattr(self, 'recovery_thread') or not self.recovery_thread.isRunning():
            return
            
        # Confirm cancellation
        confirm = QMessageBox.question(
            self,
            "Cancel Recovery",
            "Are you sure you want to cancel the password recovery process?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if confirm == QMessageBox.Yes:
            logger.info("Password recovery cancelled by user")
            self.recovery_thread.cancel()
            
            # Update UI
            self.result_label.setText("Recovery cancelled.")
            self.start_button.setEnabled(True)
            self.start_button.setText("Start Recovery")
            self.pause_button.setEnabled(False)
            self.cancel_button.setEnabled(False)
            
    def on_memory_warning(self, memory_mb):
        # Update memory usage display
        self.memory_usage_label.setText(f"Memory Usage: {memory_mb:.1f} MB (High)")
        self.memory_usage_label.setStyleSheet("color: red; font-weight: bold;")
        
        # Log warning
        logger.warning(f"High memory usage: {memory_mb:.1f} MB")


def main():
    try:
        app = QApplication(sys.argv)
        app.setStyle('Fusion')  # Modern style
        logger.info("Created QApplication with Fusion style")
        
        # Set application icon
        icon_path = os.path.join(os.path.dirname(__file__), "kanna_icon.ico")
        if os.path.exists(icon_path):
            app_icon = QIcon(icon_path)
            app.setWindowIcon(app_icon)
            logger.info(f"Set application icon from {icon_path}")
        
        window = PDFPasswordRecoveryApp()
        logger.info("Created main application window")
        
        window.show()
        logger.info("Showing main window and entering application loop")
        
        sys.exit(app.exec_())
    except Exception as e:
        logger.error(f"Application error: {e}")
        traceback.print_exc()
        QMessageBox.critical(None, "Application Error", 
                            f"An error occurred: {str(e)}\n\nSee console for details.")


if __name__ == "__main__":
    main()
