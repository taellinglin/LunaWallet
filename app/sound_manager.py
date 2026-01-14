"""Sound notification manager for wallet transactions"""
import os
import threading

try:
    import pygame
    PYGAME_AVAILABLE = True
except ImportError:
    PYGAME_AVAILABLE = False


class SoundManager:
    """Manage sound effects for wallet events"""
    
    def __init__(self):
        self.initialized = False
        self.sound_cache = {}
        
        if PYGAME_AVAILABLE:
            try:
                pygame.mixer.init()
                self.initialized = True
            except Exception as e:
                print(f"Failed to initialize pygame mixer: {e}")
    
    def _get_sound_path(self, sound_name):
        """Get absolute path to sound file"""
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        sound_path = os.path.join(base_dir, 'assets', 'sounds', f'{sound_name}.wav')
        return sound_path if os.path.exists(sound_path) else None
    
    def play_sound(self, sound_name, async_play=True):
        """Play a sound effect
        
        Args:
            sound_name: Name of sound file without extension (e.g., 'send', 'transaction')
            async_play: If True, play sound in background thread
        """
        if not PYGAME_AVAILABLE or not self.initialized:
            return False
        
        try:
            sound_path = self._get_sound_path(sound_name)
            if not sound_path:
                print(f"Sound file not found: {sound_name}.wav")
                return False
            
            # Load sound (cache it if not already loaded)
            if sound_path not in self.sound_cache:
                sound = pygame.mixer.Sound(sound_path)
                self.sound_cache[sound_path] = sound
            else:
                sound = self.sound_cache[sound_path]
            
            # Play sound
            if async_play:
                thread = threading.Thread(target=sound.play)
                thread.daemon = True
                thread.start()
            else:
                sound.play()
            
            return True
        except Exception as e:
            print(f"Error playing sound {sound_name}: {e}")
            return False
    
    def play_send_sound(self):
        """Play sound when transaction is sent"""
        self.play_sound('send')
    
    def play_transaction_sound(self):
        """Play sound when transaction is received"""
        self.play_sound('transaction')
    
    def stop_all(self):
        """Stop all currently playing sounds"""
        if PYGAME_AVAILABLE:
            try:
                pygame.mixer.stop()
            except Exception as e:
                print(f"Error stopping sounds: {e}")
    
    def cleanup(self):
        """Clean up resources"""
        self.stop_all()
        self.sound_cache.clear()
