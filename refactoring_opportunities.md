# Refactoring Opportunities & Code Quality Review

## 1. Global State & Side Effects at Import Time

**Location**: `main.py` (Lines 1-62)
**Issue**: The code executes logic (`setup_cache_directory`) and modifies environment variables at the global scope, running immediately upon import. This side-effect makes testing difficult (as importing the module triggers filesystem operations) and creates implicit dependencies.
**Recommendation**:

- **Short-term**: Move this logic into a dedicated `bootstrap.py` or `config.py` module to isolate side effects.
- **Long-term**: Refactor `lunalib` initialization to accept configuration parameters during instantiation (Dependency Injection pattern) rather than relying on environment variables or global patching.

## 2. In-Memory "Single Page" Navigation

**Location**: `main.py` (`show_wallet_page`, `show_send_page`, etc.)
**Issue**: The application manages navigation by manually clearing and rebuilding the UI control tree (`self.page.controls.clear()`). This is "brittle" (hard to maintain state), inefficient (re-renders everything), and lacks standard navigation features like history stack management.
**Recommendation**: Adopt [Flet's Routing System](https://flet.dev/docs/guides/python/navigation-and-routing). Use `page.go('/route')` and `page.views` to manage navigation state, deep linking, and transitions properly.

## 3. Monkey Patching External Libraries

**Location**: `main.py` (`LunaWalletApp._patch_lunalib_cache`, `_patch_blockchain_scanner`)
**Issue**: The code modifies `lunalib` classes and methods at runtime (`luna_cache.BlockchainCache.__init__ = patched_init`). This is highly fragile; if `lunalib` updates its internal implementation, this patch will silently break or cause crashes. It indicates the library API is insufficient for the app's needs.
**Recommendation**:

- **Best**: Submit a PR to `lunalib` or fork it to add official support for customizing cache directories and transaction logic.
- **Alternative**: Subclass the necessary components properly instead of replacing methods on the existing classes dynamically.

## 4. Heavy Logic in UI Controller

**Location**: `main.py` (`LunaWalletApp` class)
**Issue**: The `LunaWalletApp` class is becoming a "God Object". It handles UI creation, navigation, business logic (calculating balances), network calls (syncing), and persistence (saving JSON).
**Recommendation**: Apply **separation of concerns**:

- **Services**: Move blockchain syncing, balance calculation, and data persistence into dedicated Service classes (e.g., `WalletService`, `SyncService`).
- **State Management**: Use a state management approach (or even simple detailed models) so the UI doesn't hold all the application data directly.

## 5. Blocking Operations in Main Thread

**Location**: `main.py` (e.g., heavy file I/O or calculations potentially)
**Issue**: While some operations use `threading.Thread`, mixing UI updates and background logic in the same class often leads to race conditions or UI freezes if not handled carefully.

## 6. Improper Logging Mechanism

**Location**: Everywhere (e.g., `main.py`, `gui/*.py`)
**Issue**: The code relies heavily on `print()` statements for debugging and logging. In production, these are either lost (no console) or impact performance (blocking I/O). There is no log rotation, severity levels (DEBUG vs ERROR), or persistence to disk for crash analysis.

## 7. Scalability Risk in Persistence Layer

**Location**: `main.py` (`save_wallet_data`, `load_wallet_data`)
**Issue**: The entire application state (wallets, settings) is stored in a single `wallet_data.json` file. As the number of wallets grows, reading and atomically writing this entire file for every small change becomes a performance bottleneck (O(N) I/O cost).

## 8. Excessive Nested Functions & Classes

**Location**: `main.py` (e.g., `_patch_lunalib_cache`, `start_blockchain_sync`, `_create_enhanced_blockchain_manager`)
**Issue**: Key logic is buried inside helper functions or classes defined _inside_ other methods. This makes the code:

1.  **Hard to Read**: Increases indentation levels and cognitive load.
2.  **Untestable**: You cannot write unit tests for `sync_thread` or `EnhancedBlockchainManager` because they are hidden inside other scopes.
3.  **Hard to Reuse**: The logic is trapped in that specific function's scope.

## 9. Hard Dependency Coupling (Lack of Inversion of Control)

**Location**: `main.py` (`LunaWalletApp.__init__`)
**Issue**: Core components (`LunaWallet`, `BlockchainManager`, `TransactionManager`, `WalletDatabase`) are instantiated directly inside the constructor.

```python
self.wallet_core = LunaWallet()
self.blockchain_manager = BlockchainManager(...)
```

This creates tight coupling. You cannot easily swap these out for Mock objects during testing, nor can you configure them differently for different environments (Dev vs Prod) without changing the `main.py` code.

## 10. Manual Data Parsing vs. Structured Models

**Location**: Everywhere (e.g., `_find_address_transactions`, UI updates)
**Issue**: The code parses dictionaries explicitly using `tx.get('key', default)` everywhere.

```python
amount = float(tx.get('amount', 0))
fee = float(tx.get('fee', 0))
```

This is error-prone ("Stringly Typed"), tedious to write, and lacks validation.
**Recommendation**: Use **Pydantic** (Python's standard for data validation) or Python `dataclasses`.

## 11. Redundant UI Updates

**Location**: `main.py` (`update_layout` vs `show_current_page`)
**Issue**: `update_layout` calls `self.page.controls.clear()`, then calls `show_current_page()`, which _also_ calls `self.page.controls.clear()`.

```python
def update_layout(self):
    self.page.controls.clear()  # REDUNDANT
    self.show_current_page()    # This function clears it again
```

This causes unnecessary work and potentially flickering.
**Recommendation**: Remove the redundant clear/update calls in `update_layout` and let `show_current_page` handle the single source of truth for rendering.

## 12. Hardcoded Configuration & Magic Strings

**Location**: Multiple files (`main.py`, `gui/page_wallet.py`, `pyproject.toml`)
**Issue**: API endpoints (e.g., `https://bank.linglin.art`) are hardcoded strings scattered throughout the codebase.
**Risks**:

1.  **Maintenance Nightmare**: Changing the domain requires hunting down every occurrence.
2.  **Environment Inflexibility**: No easy way to switch between Dev, Staging, and Prop environments.
3.  **Typos**: A single character typo in one file can break specific features silently.

**Recommendation**: extracting these into a centralized `config.py` or use environment variables (`.env`).

## 13. Hardcoded Styles & Theme (No Reusability)

**Location**: Everywhere (`main.py`, `gui/*.py`, `utils.py`)
**Issue**: Hex color codes (e.g., `#00ff00`, `#2c1a1a`) are strings duplicated hundreds of times.
**Risks**:

1.  **Inconsistent Design**: Easy to accidentally use slightly different shades of red/green.
2.  **No Theming**: Impossible to implement "Dark/Light" mode toggles or rebrand the app without rewriting every file.
3.  **Code Duplication**: "Magic strings" clutter the UI logic.

**Recommendation**: Create a `theme.py` with a consistent Palette and Styles (e.g., `AppTheme.colors.primary`, `AppTheme.styles.header_text`).

## 14. Duplicate Method Definitions (Shadowing)

**Location**: `main.py`
**Issue**: The method `start_blockchain_sync` is defined **twice** in the `LunaWalletApp` class (once around line 1110, and again around line 1650).
**Risks**:

1.  **Silent Overwrite**: Python executes the class body linearly; the second definition silenty overwrites the first.
2.  **Developer Confusion**: A developer might edit the first definition and wonder why their changes have no effect.
3.  **Dead Code**: The first implementation is effectively dead code, bloating the file.

**Recommendation**: Delete duplication definitions immediately.
