import os
from PyPDF2 import PdfReader


class PDFPasswordRecovery:
    """
    Class for handling PDF password recovery operations
    """
    def __init__(self, pdf_path):
        """Initialize with path to the password-protected PDF file"""
        self.pdf_path = pdf_path
        
    def try_password(self, password):
        """
        Attempt to open the PDF with the given password.
        
        Args:
            password (str): The password to try
            
        Returns:
            bool: True if password is correct, False otherwise
        """
        try:
            # Try to open the PDF with the provided password
            with open(self.pdf_path, 'rb') as file:
                reader = PdfReader(file)
                
                # Check if the PDF is encrypted
                if reader.is_encrypted:
                    # Try to decrypt with the password
                    if reader.decrypt(password):
                        # Successfully decrypted
                        return True
                    else:
                        # Wrong password
                        return False
                else:
                    # PDF is not encrypted, no password needed
                    return True
        except Exception as e:
            # Handle any errors
            print(f"Error trying password: {e}")
            return False

    def validate_pdf(self):
        """
        Check if the selected file is a valid, encrypted PDF
        
        Returns:
            tuple: (is_valid, message) where is_valid is a boolean and message
                   is a descriptive message about the validation result
        """
        try:
            # Check if the file exists
            if not os.path.exists(self.pdf_path):
                return False, "File does not exist"
                
            # Check if it's actually a PDF
            with open(self.pdf_path, 'rb') as file:
                # Try to read the PDF
                try:
                    reader = PdfReader(file)
                except Exception:
                    return False, "Invalid PDF file format"
                
                # Check if it's encrypted
                if not reader.is_encrypted:
                    return False, "PDF is not password protected"
                    
                return True, "Valid password-protected PDF"
                
        except Exception as e:
            return False, f"Error: {str(e)}"
