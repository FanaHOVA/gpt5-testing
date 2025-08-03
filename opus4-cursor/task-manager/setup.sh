#!/bin/bash
# Setup script for Task Manager

echo "Task Manager Setup"
echo "=================="
echo

# Check if Python 3 is available
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is required but not found."
    exit 1
fi

# Install the package
echo "Installing task-manager package..."
pip3 install -e . || {
    echo "Error: Failed to install package. You may need to use 'sudo' or install in user mode."
    exit 1
}

# Make the tm script executable
chmod +x tm

# Determine the best location for the tm command
if [ -d "$HOME/.local/bin" ]; then
    BIN_DIR="$HOME/.local/bin"
elif [ -d "$HOME/bin" ]; then
    BIN_DIR="$HOME/bin"
else
    echo
    echo "Creating $HOME/.local/bin for user scripts..."
    mkdir -p "$HOME/.local/bin"
    BIN_DIR="$HOME/.local/bin"
fi

# Create a symlink to the tm script
echo "Creating symlink in $BIN_DIR..."
ln -sf "$(pwd)/tm" "$BIN_DIR/tm"

# Check if BIN_DIR is in PATH
if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
    echo
    echo "Note: $BIN_DIR is not in your PATH."
    echo "Add this line to your shell configuration file (~/.bashrc, ~/.zshrc, etc.):"
    echo
    echo "  export PATH=\"\$PATH:$BIN_DIR\""
    echo
    echo "Then reload your shell or run: source ~/.bashrc"
else
    echo "✓ $BIN_DIR is already in your PATH"
fi

echo
echo "Setup complete! You can now use the 'tm' command."
echo
echo "Quick test:"
echo "  tm --version"
echo "  tm --help"
echo
echo "Create your first task:"
echo "  tm create \"My first task\" --priority high"