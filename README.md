# Kanna PDF Password Recovery

<img src="screenshots/app_icon.png" alt="Kanna PDF Password Recovery Icon" width="128" height="128" align="right"/>

A user-friendly desktop application to recover passwords from protected PDF documents using a customizable password generator and brute force approach. Built with Python and PyQt5, it provides an intuitive interface for password recovery operations with real-time feedback.

## 🌟 Features

- **Easy-to-use step-by-step interface** with clean, modern UI
- **Select any password-protected PDF file** with built-in validation
- **Advanced password generation options**:
  - Customizable password length range (1-16 characters)
  - Selectable character sets (lowercase, uppercase, digits, special characters)
  - Option for unlimited password generation with safety confirmation
  - Real-time display of currently generating pattern
- **Full-featured password recovery process**:
  - Pause/resume capability for better control
  - Cancel option when needed
  - Real-time progress tracking with percentage and current password display
  - Memory usage monitoring with automatic protection
- **Responsive design** that remains interactive even with large password lists

## 📥 Installation

### Option 1: Download the Executable (Windows)

1. Go to the [Releases](https://github.com/KannaCS/pdfpasswordrecovery/releases/tag/pdf) page
2. Download the latest `.exe` file
3. Run the executable - no installation required!

### Option 2: Run from Source

1. Clone this repository:
   ```bash
   git clone https://github.com/KannaCS/pdfpasswordrecovery.git
   cd pdfpasswordrecovery
   ```

2. Install Python 3.7 or higher

3. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Run the application:
   ```bash
   python main.py
   ```

## 🔒 How It Works

1. **Select a PDF file**: Choose any password-protected PDF document
2. **Generate passwords**: Configure password parameters (length, character sets)
3. **Recover password**: The app will attempt to unlock the PDF using generated passwords

## 🛠️ Building from Source

To build a standalone executable:

```bash
# Install PyInstaller if you haven't already
pip install pyinstaller

# Run the build script
.\build_exe.bat
```

The executable will be created in the `dist` folder.

## 📋 Requirements

- Python 3.7+
- PyQt5
- PyPDF2
- psutil

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## ⚠️ Disclaimer

This tool is intended for legitimate password recovery of your own PDF documents. Do not use it to access documents you don't have permission to unlock. The developers are not responsible for any misuse of this software.

## 📝 License

This project is licensed under the MIT License - see the LICENSE file for details.

### Recovery Process

1. **Step 1**: Select your password-protected PDF file
2. **Step 2**: Configure password generation options
   - Set minimum and maximum password length
   - Select character types to include
   - Get an estimate of password list size
3. **Step 3**: Start the recovery process and monitor progress

## Notes

- For better performance, keep password list sizes reasonable
- Longer or more complex passwords will take more time to recover
- This tool is intended for legitimate password recovery of your own documents

## Requirements

- Python 3.7+
- PyQt5
- PyPDF2
