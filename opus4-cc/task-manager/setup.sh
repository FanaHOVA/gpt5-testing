#!/bin/bash
# Setup script for Task Manager

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
TM_PATH="$SCRIPT_DIR/tm"

echo "Task Manager Setup"
echo "=================="
echo

# Check if tm is already in PATH
if command -v tm &> /dev/null; then
    echo "Warning: 'tm' command already exists in PATH"
    echo "Current location: $(which tm)"
    read -p "Do you want to continue? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Create symlink option
echo "Setup options:"
echo "1. Create symlink in /usr/local/bin (requires sudo)"
echo "2. Add to PATH in shell config"
echo "3. Just show manual instructions"
echo

read -p "Choose option (1-3): " option

case $option in
    1)
        echo "Creating symlink..."
        sudo ln -sf "$TM_PATH" /usr/local/bin/tm
        if [ $? -eq 0 ]; then
            echo "✓ Symlink created successfully"
            echo "You can now use 'tm' command from anywhere"
        else
            echo "✗ Failed to create symlink"
        fi
        ;;
    2)
        echo
        echo "Add the following line to your shell config file:"
        echo "(~/.bashrc, ~/.zshrc, or similar)"
        echo
        echo "export PATH=\"$SCRIPT_DIR:\$PATH\""
        echo
        echo "Then reload your shell or run: source ~/.bashrc"
        ;;
    3)
        echo
        echo "Manual installation:"
        echo "1. Copy or symlink '$TM_PATH' to a directory in your PATH"
        echo "2. Or add '$SCRIPT_DIR' to your PATH"
        echo "3. Ensure the script has execute permissions: chmod +x $TM_PATH"
        ;;
    *)
        echo "Invalid option"
        exit 1
        ;;
esac

echo
echo "Setup complete! Try running: tm add \"My first task\""