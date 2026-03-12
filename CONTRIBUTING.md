# Contributing to Lavida

Thanks for your interest in contributing to Lavida! Here's how you can help.

## Getting Started

1. Fork the repository
2. Clone your fork:
   ```bash
   git clone https://github.com/<your-username>/lavida.git
   cd lavida
   ```
3. Create a virtual environment and install dependencies:
   ```bash
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```
4. Create a branch for your work:
   ```bash
   git checkout -b your-feature-name
   ```

## Development

Run the app locally:

```bash
python main.py
```

The app uses:
- **PyQt6** for the UI
- **SQLite** for local persistence (`lavida.db`, auto-created)
- **pynput** for global input listening (toggle visibility)
- **requests + BeautifulSoup** for fetching YouTube metadata

### Project Structure

```
lavida/
  main.py              # Entry point
  src/
    ui/
      main_window.py   # Main application window
      widgets.py       # VideoCard, DraggableListWidget, etc.
    workers.py         # Background threads (global input listener)
    database.py        # Database helpers
```

## Submitting Changes

1. Keep commits focused and descriptive
2. Test your changes locally before submitting
3. Open a pull request against `main` with a clear description of what you changed and why
4. Link any related issues

## Reporting Bugs

Open an issue with:
- Steps to reproduce
- Expected vs actual behavior
- Your OS and Python version

## Code Style

- Follow existing patterns in the codebase
- Use meaningful variable names
- Keep functions focused and short
- No unnecessary dependencies

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
