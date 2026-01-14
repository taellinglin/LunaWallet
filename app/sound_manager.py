"""Sound notification manager for wallet transactions - Cross-platform support"""
import os
import threading
import platform
import sys

# Try multiple audio backends based on platform
AUDIO_BACKEND = None

# Try pygame first (cross-platform)
try:
    import pygame
    AUDIO_BACKEND = 'pygame'
except ImportError:
    pass

# On Windows, try winsound as fallback
if not AUDIO_BACKEND and platform.system() == 'Windows':
    try:
        import winsound
        AUDIO_BACKEND = 'winsound'
    except ImportError:
        pass

# For Flet/mobile apps, check if flet is available
FLET_AVAILABLE = False
try:
    import flet as ft
    FLET_AVAILABLE = True
except ImportError:
    pass


class SoundManager:
    """Manage sound effects for wallet events - Cross-platform support"""
    
    def __init__(self):
        self.initialized = False
        self.sound_cache = {}
        self.backend = AUDIO_BACKEND
        self.is_mobile = self._detect_mobile()
        
        # Initialize the appropriate backend
        if self.backend == 'pygame':
            try:
                pygame.mixer.init()
                # Allocate enough channels for simultaneous sound plays
                pygame.mixer.set_num_channels(8)
                self.initialized = True
                print(f"DEBUG: SoundManager initialized with pygame backend (cross-platform)")
            except Exception as e:
                print(f"DEBUG: Failed to initialize pygame mixer: {e}")
                self.backend = None
        elif self.backend == 'winsound':
            self.initialized = True
            print(f"DEBUG: SoundManager initialized with winsound backend (Windows only)")
        elif self.is_mobile and FLET_AVAILABLE:
            self.initialized = True
            print(f"DEBUG: SoundManager initialized for mobile/Flet")
        else:
            print(f"DEBUG: No audio backend available")
    
    def _detect_mobile(self):
        """Detect if running on mobile platform (Android/iOS)"""
        # Check for Flet running on mobile
        if FLET_AVAILABLE:
            try:
                # In a Flet app, we can check the platform
                if hasattr(sys, 'platform'):
                    if 'android' in sys.platform or 'ios' in sys.platform:
                        return True
            except:
                pass
        return False
    
    def _get_sound_path(self, sound_name):
        """Get absolute path to sound file"""
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        sound_path = os.path.join(base_dir, 'assets', 'sounds', f'{sound_name}.wav')
        if os.path.exists(sound_path):
            return sound_path
        else:
            print(f"DEBUG: Sound file not found at {sound_path}")
            return None
    
    def play_sound(self, sound_name, async_play=True):
        """Play a sound effect - Works on Windows, macOS, Linux, and Android
        
        Args:
            sound_name: Name of sound file without extension (e.g., 'send', 'transaction')
            async_play: If True, play sound in background thread
        """
        if not self.initialized:
            print(f"DEBUG: SoundManager not initialized, cannot play {sound_name}")
            return False
        
        try:
            sound_path = self._get_sound_path(sound_name)
            if not sound_path:
                return False
            
            print(f"DEBUG: Playing sound: {sound_path} (backend: {self.backend}, mobile: {self.is_mobile})")
            
            if self.backend == 'pygame':
                return self._play_with_pygame(sound_path, async_play)
            elif self.backend == 'winsound':
                return self._play_with_winsound(sound_path, async_play)
            elif self.is_mobile and FLET_AVAILABLE:
                return self._play_with_flet(sound_path, async_play)
            else:
                print(f"DEBUG: No valid audio backend for playback")
                return False
        except Exception as e:
            print(f"DEBUG: Error playing sound {sound_name}: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _play_with_pygame(self, sound_path, async_play=True):
        """Play sound using pygame mixer - Works on Windows, macOS, Linux
        
        This is the recommended backend for desktop platforms and has the widest compatibility.
        """
        try:
            # Always load fresh sound to allow rapid successive plays
            # Don't use cache for pygame as it prevents rapid replays
            sound = pygame.mixer.Sound(sound_path)
            
            # Play sound using a dedicated channel to avoid conflicts
            # Find an available channel or allocate a new one
            try:
                # Use a specific channel (e.g., channel 0) to allow multiple simultaneous plays
                channel = pygame.mixer.find_channel()
                if channel:
                    channel.play(sound)
                else:
                    # If no channel available, allocate more channels and retry
                    pygame.mixer.set_num_channels(pygame.mixer.get_num_channels() + 1)
                    channel = pygame.mixer.find_channel()
                    if channel:
                        channel.play(sound)
                    else:
                        # Fallback to direct play
                        sound.play()
            except:
                # Fallback if channel approach fails
                sound.play()
            
            print(f"DEBUG: Sound played successfully with pygame (fresh load)")
            return True
        except Exception as e:
            print(f"DEBUG: Error playing with pygame: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _play_with_winsound(self, sound_path, async_play=True):
        """Play sound using Windows native winsound - Windows only
        
        This uses Windows' built-in sound system and doesn't require external dependencies.
        """
        try:
            import winsound
            
            def play():
                try:
                    # SND_FILENAME flag tells winsound to play from file
                    # Use SND_ASYNC to play asynchronously (non-blocking)
                    winsound.PlaySound(sound_path, winsound.SND_FILENAME | winsound.SND_ASYNC)
                    print(f"DEBUG: Sound played successfully with winsound")
                except Exception as e:
                    print(f"DEBUG: Error in winsound playback: {e}")
            
            if async_play:
                thread = threading.Thread(target=play)
                thread.daemon = True
                thread.start()
            else:
                play()
            
            return True
        except Exception as e:
            print(f"DEBUG: Error playing with winsound: {e}")
            return False
    
    def _play_with_flet(self, sound_path, async_play=True):
        """Play sound using Flet's audio capabilities - Android, iOS, Web
        
        This uses Flet's built-in Audio control which works on mobile platforms.
        Note: Requires the sound to be accessible to Flet.
        """
        try:
            import flet as ft
            
            # For Flet apps, we need to use the Audio control
            # This is a workaround - ideally should be called from within a Flet page context
            print(f"DEBUG: Flet audio playback not directly supported from background thread")
            print(f"DEBUG: Consider using platform-specific audio APIs or embedding audio control in Flet app")
            
            # Try using pygame as fallback on mobile
            if self.backend == 'pygame':
                return self._play_with_pygame(sound_path, async_play)
            
            return False
        except Exception as e:
            print(f"DEBUG: Error playing with Flet: {e}")
            return False
    
    def play_send_sound(self):
        """Play sound when transaction is sent"""
        print("DEBUG: play_send_sound() called")
        return self.play_sound('send')
    
    def play_transaction_sound(self):
        """Play sound when transaction is received"""
        print("DEBUG: play_transaction_sound() called")
        return self.play_sound('transaction')
    
    def stop_all(self):
        """Stop all currently playing sounds"""
        if self.backend == 'pygame':
            try:
                pygame.mixer.stop()
                print("DEBUG: Stopped all sounds (pygame)")
            except Exception as e:
                print(f"DEBUG: Error stopping sounds: {e}")
    
    def cleanup(self):
        """Clean up resources"""
        self.stop_all()
        self.sound_cache.clear()


