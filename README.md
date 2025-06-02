# Telegram-Restricted-Content-Downloader

A Telegram bot designed to streamline the process of downloading restricted and non-restricted content from Telegram groups and channels. Now available with both command-line and graphical user interfaces!

<div align="center">
  <img src="./example/screenshot.png" alt="screenshot" width="300">
</div>

## Features

📋 **Clipboard Monitoring**: Detects and adds Telegram media links automatically  
📥 **Restricted/Non-Restricted Downloads**: Supports private and public content  
⏸ **Queue Management**: Collects links until you're ready to download  
🔄 **Reset**: Clear the list anytime  
🖥️ **Modern GUI**: Beautiful graphical interface with progress bars and error handling  
📊 **Export Features**: Export message ranges to HTML or JSON with parallel processing  
📈 **Statistics**: Track your downloads with detailed statistics  

## Interface Options

### Graphical User Interface (Recommended)
Launch the modern GUI application:
```bash
python run_gui.py
```

**GUI Features:**
- 🎨 Modern dark theme interface
- 📊 Real-time progress bars with cancellation support
- 📋 Clipboard monitoring with visual feedback
- 🔧 Message range export tools (HTML/JSON)
- 📈 Download statistics and file management
- ⚠️ Error dialogs with copy-to-clipboard functionality
- 🖱️ Point-and-click operation for all features

### Command Line Interface
Use the traditional CLI:
```bash
python app.py
```

## GUI Usage Guide

### 1. Download Tab
- **Clipboard Monitoring**: Click "Start Monitoring" to automatically detect Telegram links
- **Manual Entry**: Add links manually using the text field
- **Queue Management**: View, remove, or clear queued links
- **Batch Download**: Download all queued content with progress tracking

### 2. Export Tab
- **Message Range Export**: Enter start and end message links
- **HTML Export**: Creates interactive HTML with media, CSS, and JavaScript files
- **JSON Export**: Fast export of message metadata without media download
- **Export Log**: Track export operations and errors

### 3. Statistics Tab
- **Download Summary**: View total files downloaded by type
- **Recent Files**: See your most recent downloads
- **File Organization**: Review how content is organized in folders

## Error Handling

The GUI provides comprehensive error handling:
- 🚨 **Error Dialogs**: Detailed error messages with technical details
- 📋 **Copy Support**: Copy error details to clipboard for troubleshooting
- 🔄 **Recovery Options**: Graceful handling of connection issues
- 📝 **Error Logging**: Track issues in export operations

# Requirements

Ensure you have Python 3.8+ installed. Install the following dependencies:

```bash
pyaes==1.6.1
pyperclip==1.9.0
pyrotgfork==2.2.12
PySocks==1.7.1
PyTgCrypto==1.2.6
python-dotenv==1.0.1
TgCrypto==1.2.5
customtkinter==5.2.2
```

## Installation

### 1. Clone this repository:

```bash
git clone https://github.com/victorjalonzo/Telegram-Restricted-Content-Downloader.git
cd Telegram-Restricted-Content-Downloader
```

### 2. Install dependencies:

```bash
pip install -r requirements.txt
```

### 3. Create a .env file in the project's root directory with the following content:

```bash
#Replace it with your Telegram application credentials
API_ID="YOUR_API_ID"
API_HASH="YOUR_API_HASH"
```
Replace the placeholders with your corresponding information.
If you don't have these credentials, visit https://my.telegram.org/auth to obtain them.

## Usage

### GUI Application (Recommended)
To start the graphical interface:
```bash
python run_gui.py
```

### Command Line Application
To start the CLI version:
```bash
python app.py
```

### CLI Commands
When using the command line interface:
- `[Enter]` - Download all queued links
- `r` - Reset queue
- `export <start_link> <end_link>` - Export message range to HTML with media
- `json <start_link> <end_link>` - Export message range to JSON only
- `stats` - Show download statistics
- `exit` - Exit application

## File Organization

Downloaded content is automatically organized into:
- `downloads/media/` - Media files (photos, videos, audio)
- `downloads/text/` - Text-only messages
- `downloads/captions/` - Media captions
- `downloads/service_messages/` - Service/system messages
- `downloads/exports/` - HTML and JSON exports

## Contributions

Contributions are welcome. If you'd like to contribute, please fork the repository and create a pull request with your changes.

## License

This project is licensed under the MIT License. See the LICENSE file for details.