"""Debug logging utility for built executables"""
import os
import sys
from datetime import datetime

class DebugLogger:
    """Logger that writes to a file for debugging built executables"""
    
    def __init__(self):
        self.log_file = None
        self.enabled = True
        self._init_log_file()
    
    def _init_log_file(self):
        """Initialize log file in user's temp directory"""
        try:
            # Get a writable directory
            if hasattr(sys, '_MEIPASS'):
                # Running as built executable
                log_dir = os.path.join(os.path.expanduser('~'), 'LunaWallet_Logs')
            else:
                # Running as script
                log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs')
            
            os.makedirs(log_dir, exist_ok=True)
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            log_path = os.path.join(log_dir, f'debug_{timestamp}.log')
            
            self.log_file = open(log_path, 'w', encoding='utf-8')
            self.log(f"Debug log initialized at {log_path}")
            self.log(f"Running as built executable: {hasattr(sys, '_MEIPASS')}")
            
        except Exception as e:
            print(f"Failed to initialize debug log: {e}")
            self.enabled = False
    
    def log(self, message):
        """Write a log message"""
        if not self.enabled or not self.log_file:
            return
        
        try:
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
            self.log_file.write(f"[{timestamp}] {message}\n")
            self.log_file.flush()
        except Exception as e:
            print(f"Failed to write log: {e}")
    
    def close(self):
        """Close the log file"""
        if self.log_file:
            try:
                self.log_file.close()
            except:
                pass

# Global logger instance
_logger = None

def get_logger():
    """Get or create the global logger instance"""
    global _logger
    if _logger is None:
        _logger = DebugLogger()
    return _logger

def debug_log(message):
    """Convenience function to log a debug message"""
    logger = get_logger()
    logger.log(message)
    # Also print to console if available
    print(message)
