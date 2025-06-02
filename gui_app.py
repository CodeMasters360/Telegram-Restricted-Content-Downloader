import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import customtkinter as ctk
import asyncio
import threading
import pyperclip
import time
from typing import List
import os
from datetime import datetime

from src.client import Client
from src.fileManager import FileManager
from src.exceptions import NoContinueException

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

class ModernProgressDialog:
    def __init__(self, parent, title="Processing..."):
        self.dialog = ctk.CTkToplevel(parent)
        self.dialog.title(title)
        self.dialog.geometry("400x150")
        self.dialog.resizable(False, False)
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        # Center the dialog
        self.dialog.geometry("+%d+%d" % (parent.winfo_rootx() + 50, parent.winfo_rooty() + 50))
        
        # Progress label
        self.progress_label = ctk.CTkLabel(self.dialog, text="Initializing...", font=ctk.CTkFont(size=12))
        self.progress_label.pack(pady=(20, 10))
        
        # Progress bar
        self.progress_bar = ctk.CTkProgressBar(self.dialog, width=350)
        self.progress_bar.pack(pady=10)
        self.progress_bar.set(0)
        
        # Cancel button
        self.cancel_button = ctk.CTkButton(self.dialog, text="Cancel", command=self.cancel)
        self.cancel_button.pack(pady=10)
        
        self.cancelled = False
    
    def update_progress(self, value, text=""):
        if text:
            self.progress_label.configure(text=text)
        self.progress_bar.set(value)
        self.dialog.update()
    
    def cancel(self):
        self.cancelled = True
        self.dialog.destroy()
    
    def close(self):
        if self.dialog.winfo_exists():
            self.dialog.destroy()

class ErrorDialog:
    def __init__(self, parent, title, message, error_details=None):
        self.dialog = ctk.CTkToplevel(parent)
        self.dialog.title(title)
        self.dialog.geometry("500x400")
        self.dialog.resizable(True, True)
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        # Center the dialog
        self.dialog.geometry("+%d+%d" % (parent.winfo_rootx() + 100, parent.winfo_rooty() + 100))
        
        # Main message
        message_label = ctk.CTkLabel(self.dialog, text=message, font=ctk.CTkFont(size=14, weight="bold"))
        message_label.pack(pady=(20, 10), padx=20)
        
        if error_details:
            # Error details text area
            details_frame = ctk.CTkFrame(self.dialog)
            details_frame.pack(pady=10, padx=20, fill="both", expand=True)
            
            details_label = ctk.CTkLabel(details_frame, text="Error Details:", font=ctk.CTkFont(size=12, weight="bold"))
            details_label.pack(pady=(10, 5), anchor="w")
            
            self.details_text = ctk.CTkTextbox(details_frame, height=200)
            self.details_text.pack(pady=5, padx=10, fill="both", expand=True)
            self.details_text.insert("1.0", str(error_details))
            self.details_text.configure(state="disabled")
        
        # Button frame
        button_frame = ctk.CTkFrame(self.dialog, fg_color="transparent")
        button_frame.pack(pady=10, fill="x")
        
        # Copy button
        if error_details:
            copy_button = ctk.CTkButton(button_frame, text="Copy Error", command=self.copy_error)
            copy_button.pack(side="left", padx=(20, 10))
        
        # OK button
        ok_button = ctk.CTkButton(button_frame, text="OK", command=self.dialog.destroy)
        ok_button.pack(side="right", padx=(10, 20))
        
        self.error_text = f"{message}\n\nDetails:\n{error_details}" if error_details else message
    
    def copy_error(self):
        try:
            pyperclip.copy(self.error_text)
            # Show brief confirmation
            temp_button = ctk.CTkButton(self.dialog, text="Copied!", state="disabled")
            temp_button.place(x=20, y=20)
            self.dialog.after(1000, temp_button.destroy)
        except Exception as e:
            print(f"Failed to copy error: {e}")

class TelegramDownloaderGUI:
    def __init__(self):
        self.root = ctk.CTk()
        self.root.title("Telegram Content Downloader")
        self.root.geometry("800x600")
        
        # Initialize variables
        self.links = []
        self.client = None
        self.clipboard_monitoring = False
        self.last_clipboard_text = ""
        
        self.setup_ui()
        self.setup_directories()
        
    def setup_directories(self):
        """Setup download directories on startup"""
        try:
            FileManager.setup_directories()
        except Exception as e:
            self.show_error("Setup Error", "Failed to create directories", str(e))
    
    def setup_ui(self):
        # Main container
        main_frame = ctk.CTkFrame(self.root)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Title
        title_label = ctk.CTkLabel(main_frame, text="Telegram Content Downloader", 
                                  font=ctk.CTkFont(size=24, weight="bold"))
        title_label.pack(pady=(20, 30))
        
        # Notebook for tabs
        self.notebook = ctk.CTkTabview(main_frame)
        self.notebook.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Create tabs
        self.setup_download_tab()
        self.setup_export_tab()
        self.setup_stats_tab()
        
        # Status bar
        self.status_frame = ctk.CTkFrame(self.root, height=30)
        self.status_frame.pack(fill="x", side="bottom")
        self.status_frame.pack_propagate(False)
        
        self.status_label = ctk.CTkLabel(self.status_frame, text="Ready", font=ctk.CTkFont(size=12))
        self.status_label.pack(side="left", padx=10, pady=5)
        
        # Connection status
        self.connection_label = ctk.CTkLabel(self.status_frame, text="Disconnected", 
                                           font=ctk.CTkFont(size=12))
        self.connection_label.pack(side="right", padx=10, pady=5)
        
        # Start client connection in background
        threading.Thread(target=self.initialize_client, daemon=True).start()
    
    def setup_download_tab(self):
        tab = self.notebook.add("Download")
        
        # Clipboard monitoring section
        clipboard_frame = ctk.CTkFrame(tab)
        clipboard_frame.pack(fill="x", padx=20, pady=10)
        
        clipboard_label = ctk.CTkLabel(clipboard_frame, text="Clipboard Monitoring", 
                                     font=ctk.CTkFont(size=16, weight="bold"))
        clipboard_label.pack(pady=10)
        
        self.monitor_button = ctk.CTkButton(clipboard_frame, text="Start Monitoring", 
                                          command=self.toggle_clipboard_monitoring)
        self.monitor_button.pack(pady=5)
        
        # Manual link entry
        manual_frame = ctk.CTkFrame(tab)
        manual_frame.pack(fill="x", padx=20, pady=10)
        
        manual_label = ctk.CTkLabel(manual_frame, text="Manual Link Entry", 
                                  font=ctk.CTkFont(size=16, weight="bold"))
        manual_label.pack(pady=10)
        
        entry_frame = ctk.CTkFrame(manual_frame, fg_color="transparent")
        entry_frame.pack(fill="x", padx=20, pady=5)
        
        self.link_entry = ctk.CTkEntry(entry_frame, placeholder_text="Enter Telegram link here...")
        self.link_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        
        add_button = ctk.CTkButton(entry_frame, text="Add Link", command=self.add_manual_link)
        add_button.pack(side="right")
        
        # Links list
        links_frame = ctk.CTkFrame(tab)
        links_frame.pack(fill="both", expand=True, padx=20, pady=10)
        
        links_label = ctk.CTkLabel(links_frame, text="Queued Links", 
                                 font=ctk.CTkFont(size=16, weight="bold"))
        links_label.pack(pady=10)
        
        self.links_listbox = tk.Listbox(links_frame, height=8)
        scrollbar = ttk.Scrollbar(links_frame, orient="vertical", command=self.links_listbox.yview)
        self.links_listbox.configure(yscrollcommand=scrollbar.set)
        
        listbox_frame = ctk.CTkFrame(links_frame, fg_color="transparent")
        listbox_frame.pack(fill="both", expand=True, padx=20, pady=5)
        
        self.links_listbox.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Control buttons
        button_frame = ctk.CTkFrame(tab, fg_color="transparent")
        button_frame.pack(fill="x", padx=20, pady=10)
        
        self.download_button = ctk.CTkButton(button_frame, text="Download All", 
                                           command=self.start_download)
        self.download_button.pack(side="left", padx=(0, 10))
        
        clear_button = ctk.CTkButton(button_frame, text="Clear Queue", command=self.clear_links)
        clear_button.pack(side="left", padx=10)
        
        remove_button = ctk.CTkButton(button_frame, text="Remove Selected", 
                                    command=self.remove_selected_link)
        remove_button.pack(side="left", padx=10)
    
    def setup_export_tab(self):
        tab = self.notebook.add("Export")
        
        # Export section
        export_frame = ctk.CTkFrame(tab)
        export_frame.pack(fill="x", padx=20, pady=20)
        
        export_label = ctk.CTkLabel(export_frame, text="Message Range Export", 
                                  font=ctk.CTkFont(size=16, weight="bold"))
        export_label.pack(pady=15)
        
        # Start link
        start_frame = ctk.CTkFrame(export_frame, fg_color="transparent")
        start_frame.pack(fill="x", padx=20, pady=5)
        
        start_label = ctk.CTkLabel(start_frame, text="Start Link:", font=ctk.CTkFont(size=12))
        start_label.pack(side="left", padx=(0, 10))
        
        self.start_link_entry = ctk.CTkEntry(start_frame, placeholder_text="https://t.me/...")
        self.start_link_entry.pack(side="right", fill="x", expand=True)
        
        # End link
        end_frame = ctk.CTkFrame(export_frame, fg_color="transparent")
        end_frame.pack(fill="x", padx=20, pady=5)
        
        end_label = ctk.CTkLabel(end_frame, text="End Link:", font=ctk.CTkFont(size=12))
        end_label.pack(side="left", padx=(0, 10))
        
        self.end_link_entry = ctk.CTkEntry(end_frame, placeholder_text="https://t.me/...")
        self.end_link_entry.pack(side="right", fill="x", expand=True)
        
        # Export buttons
        export_button_frame = ctk.CTkFrame(export_frame, fg_color="transparent")
        export_button_frame.pack(pady=20)
        
        html_export_button = ctk.CTkButton(export_button_frame, text="Export to HTML", 
                                         command=self.export_to_html)
        html_export_button.pack(side="left", padx=10)
        
        json_export_button = ctk.CTkButton(export_button_frame, text="Export to JSON", 
                                         command=self.export_to_json)
        json_export_button.pack(side="left", padx=10)
        
        # Export options
        options_frame = ctk.CTkFrame(tab)
        options_frame.pack(fill="x", padx=20, pady=10)
        
        options_label = ctk.CTkLabel(options_frame, text="Export Options", 
                                   font=ctk.CTkFont(size=16, weight="bold"))
        options_label.pack(pady=15)
        
        self.download_media_var = ctk.BooleanVar(value=True)
        media_checkbox = ctk.CTkCheckBox(options_frame, text="Download media files", 
                                       variable=self.download_media_var)
        media_checkbox.pack(pady=5)
        
        # Export log
        log_frame = ctk.CTkFrame(tab)
        log_frame.pack(fill="both", expand=True, padx=20, pady=10)
        
        log_label = ctk.CTkLabel(log_frame, text="Export Log", 
                               font=ctk.CTkFont(size=16, weight="bold"))
        log_label.pack(pady=10)
        
        self.export_log = ctk.CTkTextbox(log_frame, height=150)
        self.export_log.pack(fill="both", expand=True, padx=20, pady=10)
    
    def setup_stats_tab(self):
        tab = self.notebook.add("Statistics")
        
        # Stats frame
        stats_frame = ctk.CTkFrame(tab)
        stats_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        stats_label = ctk.CTkLabel(stats_frame, text="Download Statistics", 
                                 font=ctk.CTkFont(size=16, weight="bold"))
        stats_label.pack(pady=15)
        
        self.stats_text = ctk.CTkTextbox(stats_frame, height=300)
        self.stats_text.pack(fill="both", expand=True, padx=20, pady=10)
        
        refresh_button = ctk.CTkButton(stats_frame, text="Refresh Statistics", 
                                     command=self.refresh_stats)
        refresh_button.pack(pady=10)
        
        # Load initial stats
        self.refresh_stats()
    
    def initialize_client(self):
        """Initialize Telegram client in background"""
        try:
            self.update_status("Connecting to Telegram...")
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            self.client = Client()
            loop.run_until_complete(self.client.start())
            
            self.update_status("Connected to Telegram")
            self.connection_label.configure(text="Connected", text_color="green")
        except Exception as e:
            self.update_status("Connection failed")
            self.connection_label.configure(text="Connection Failed", text_color="red")
            self.show_error("Connection Error", "Failed to connect to Telegram", str(e))
    
    def toggle_clipboard_monitoring(self):
        """Toggle clipboard monitoring"""
        if not self.clipboard_monitoring:
            self.clipboard_monitoring = True
            self.monitor_button.configure(text="Stop Monitoring")
            threading.Thread(target=self.monitor_clipboard, daemon=True).start()
            self.update_status("Clipboard monitoring started")
        else:
            self.clipboard_monitoring = False
            self.monitor_button.configure(text="Start Monitoring")
            self.update_status("Clipboard monitoring stopped")
    
    def monitor_clipboard(self):
        """Monitor clipboard for Telegram links"""
        while self.clipboard_monitoring:
            try:
                current_text = pyperclip.paste()
                
                if (current_text.startswith("https://t.me/") and 
                    current_text.strip() and 
                    current_text != self.last_clipboard_text and 
                    current_text not in self.links):
                    
                    self.last_clipboard_text = current_text
                    self.links.append(current_text)
                    self.update_links_display()
                    self.update_status(f"Link detected: {len(self.links)} links in queue")
                    
            except Exception as e:
                print(f"Clipboard monitoring error: {e}")
            
            time.sleep(0.5)
    
    def add_manual_link(self):
        """Add link manually from entry field"""
        link = self.link_entry.get().strip()
        if link.startswith("https://t.me/") and link not in self.links:
            self.links.append(link)
            self.link_entry.delete(0, 'end')
            self.update_links_display()
            self.update_status(f"Link added: {len(self.links)} links in queue")
        elif link in self.links:
            messagebox.showwarning("Duplicate Link", "This link is already in the queue.")
        else:
            messagebox.showerror("Invalid Link", "Please enter a valid Telegram link.")
    
    def update_links_display(self):
        """Update the links listbox"""
        self.links_listbox.delete(0, 'end')
        for i, link in enumerate(self.links, 1):
            display_text = f"{i}. {link}"
            if len(display_text) > 80:
                display_text = display_text[:77] + "..."
            self.links_listbox.insert('end', display_text)
    
    def clear_links(self):
        """Clear all links from queue"""
        self.links.clear()
        self.update_links_display()
        self.update_status("Queue cleared")
    
    def remove_selected_link(self):
        """Remove selected link from queue"""
        selection = self.links_listbox.curselection()
        if selection:
            index = selection[0]
            removed_link = self.links.pop(index)
            self.update_links_display()
            self.update_status(f"Removed link: {removed_link[:50]}...")
    
    def start_download(self):
        """Start downloading all queued links"""
        if not self.links:
            messagebox.showwarning("No Links", "No links in queue to download.")
            return
        
        if not self.client:
            messagebox.showerror("Not Connected", "Not connected to Telegram. Please wait for connection.")
            return
        
        # Start download in background thread
        threading.Thread(target=self.download_links_async, daemon=True).start()
    
    def download_links_async(self):
        """Download links asynchronously"""
        try:
            # Create progress dialog
            progress_dialog = ModernProgressDialog(self.root, "Downloading Content")
            
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # Run download with progress updates
            total_links = len(self.links)
            
            for i, link in enumerate(self.links):
                if progress_dialog.cancelled:
                    break
                
                progress = (i + 1) / total_links
                progress_dialog.update_progress(progress, f"Downloading {i+1}/{total_links}: {link[:40]}...")
                
                try:
                    message = loop.run_until_complete(self.client._get_media_by_link(link))
                    if message:
                        loop.run_until_complete(self.client.download_media([link]))
                except Exception as e:
                    print(f"Error downloading {link}: {e}")
            
            progress_dialog.close()
            
            if not progress_dialog.cancelled:
                # Show completion message
                stats = FileManager.get_download_stats()
                messagebox.showinfo("Download Complete", 
                                  f"Download completed!\n\n"
                                  f"Total files: {stats['total_files']}\n"
                                  f"Media files: {stats['media_files']}\n"
                                  f"Text files: {stats['text_files']}")
                
                self.clear_links()
                self.refresh_stats()
            
            self.update_status("Download completed" if not progress_dialog.cancelled else "Download cancelled")
            
        except Exception as e:
            self.show_error("Download Error", "Failed to download content", str(e))
    
    def export_to_html(self):
        """Export message range to HTML"""
        start_link = self.start_link_entry.get().strip()
        end_link = self.end_link_entry.get().strip()
        
        if not start_link or not end_link:
            messagebox.showerror("Missing Links", "Please provide both start and end links.")
            return
        
        if not self.client:
            messagebox.showerror("Not Connected", "Not connected to Telegram.")
            return
        
        threading.Thread(target=self.export_html_async, args=(start_link, end_link), daemon=True).start()
    
    def export_html_async(self, start_link, end_link):
        """Export to HTML asynchronously"""
        try:
            progress_dialog = ModernProgressDialog(self.root, "Exporting to HTML")
            
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # Update client's exporter with progress callback
            self.client.exporter.progress_callback = lambda text: progress_dialog.update_progress(0.5, text)
            
            result = loop.run_until_complete(self.client.export_message_range(start_link, end_link))
            
            progress_dialog.close()
            
            if result:
                messagebox.showinfo("Export Complete", f"HTML export completed!\nFile: {result}")
                self.log_export_message(f"HTML export successful: {result}")
            else:
                messagebox.showerror("Export Failed", "HTML export failed.")
                self.log_export_message("HTML export failed")
            
        except Exception as e:
            self.show_error("Export Error", "Failed to export to HTML", str(e))
            self.log_export_message(f"HTML export error: {str(e)}")
    
    def export_to_json(self):
        """Export message range to JSON"""
        start_link = self.start_link_entry.get().strip()
        end_link = self.end_link_entry.get().strip()
        
        if not start_link or not end_link:
            messagebox.showerror("Missing Links", "Please provide both start and end links.")
            return
        
        if not self.client:
            messagebox.showerror("Not Connected", "Not connected to Telegram.")
            return
        
        threading.Thread(target=self.export_json_async, args=(start_link, end_link), daemon=True).start()
    
    def export_json_async(self, start_link, end_link):
        """Export to JSON asynchronously"""
        try:
            progress_dialog = ModernProgressDialog(self.root, "Exporting to JSON")
            progress_dialog.update_progress(0.1, "Starting JSON export...")
            
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            result = loop.run_until_complete(self.client.export_json_only(start_link, end_link))
            
            progress_dialog.close()
            
            if result:
                messagebox.showinfo("Export Complete", f"JSON export completed!\nFile: {result}")
                self.log_export_message(f"JSON export successful: {result}")
            else:
                messagebox.showerror("Export Failed", "JSON export failed.")
                self.log_export_message("JSON export failed")
            
        except Exception as e:
            self.show_error("Export Error", "Failed to export to JSON", str(e))
            self.log_export_message(f"JSON export error: {str(e)}")
    
    def log_export_message(self, message):
        """Add message to export log"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] {message}\n"
        self.export_log.insert("end", log_entry)
        self.export_log.see("end")
    
    def refresh_stats(self):
        """Refresh download statistics"""
        try:
            stats = FileManager.get_download_stats()
            recent_files = FileManager.list_recent_files(limit=10)
            
            stats_text = f"""Download Statistics:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 File Summary:
   Total files: {stats['total_files']}
   Media files: {stats['media_files']}
   Text files: {stats['text_files']}
   Caption files: {stats['caption_files']}
   Service messages: {stats['service_files']}

📁 Recent Downloads:
"""
            
            if recent_files:
                for i, file_path in enumerate(recent_files, 1):
                    file_name = os.path.basename(file_path)
                    stats_text += f"   {i}. {file_name}\n"
            else:
                stats_text += "   No recent downloads\n"
            
            self.stats_text.delete("1.0", "end")
            self.stats_text.insert("1.0", stats_text)
            
        except Exception as e:
            self.show_error("Stats Error", "Failed to load statistics", str(e))
    
    def update_status(self, message):
        """Update status bar message"""
        self.status_label.configure(text=message)
        self.root.update_idletasks()
    
    def show_error(self, title, message, details=None):
        """Show error dialog with copy functionality"""
        ErrorDialog(self.root, title, message, details)
    
    def run(self):
        """Start the GUI application"""
        self.root.mainloop()

if __name__ == "__main__":
    app = TelegramDownloaderGUI()
    app.run()
