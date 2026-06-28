# Voice Expense Manager

An AI-powered personal finance manager featuring cross-platform voice command capabilities and a real-time dashboard visualizer. Speak or type naturally to log income, track expenses, and manage fund transfers across your accounts.

---

## Key Features

- **Natural Language Command Processing**: Powered by a local Llama-3.2-3B model to analyze inputs, resolve context dates, extract fields, and execute database operations.
- **Dynamic Voice Visualizer**: Premium Siri-style sine wave animation showing listening levels.
- **Real-Time Financial Dashboard**:
  - **KPI Cards**: Dynamic tracking of Net Assets, Total Income, and Total Expenses.
  - **Account Balances**: Dynamically computed current values across all accounts.
  - **Recent Transactions**: Scrollable transaction list with custom iconography.
- **Interactive Quick Templates**: Execute common operations (e.g. coffee purchases, salary deposits) with a single click.
- **Multi-OS Responsive Layout**: Handles window scaling dynamically. Stacks panels vertically when window width drops below `950px` (mobile layout) and displays them side-by-side on larger displays (desktop layout).
- **Cross-Platform Audio Recording**: Out-of-the-box support for macOS/Windows/Linux using `sounddevice`, with native Windows MCI (`winmm`) and Linux `arecord` fallback systems.
- **Text-to-Speech (TTS) Confirmation**: Verbally reads transaction confirmations back to the user.

---

## File Structure

- `voice_app.py`: CustomTkinter desktop interface, database bindings, visual animations, and recording workers.
- `function_calling.py`: Local LLM initialization, natural language parser, and database transaction queries (`add_income`, `add_expense`, `add_transfer`).
- `requirements.txt`: Third-party Python dependencies list.
- `ritul.db`: SQLite database storing accounts and transactions.

---

## Installation & Setup

### 1. Prerequisites
- Python 3.10+
- PortAudio (on Linux, install it via: `sudo apt-get install libportaudio2`)

### 2. Install Dependencies
Set up your virtual environment and install the required libraries:
```bash
# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install required packages
pip install -r requirements.txt
```

---

## How to Run

Launch the Voice Dashboard:
```bash
python voice_app.py
```
On first launch, the local Llama-3.2-3B-Instruct model will automatically download from HuggingFace to your local cache. Once loaded, the status badge will update to **READY**.

### Examples of spoken/typed commands:
- *"I spent $25 from Wallet on Groceries today"*
- *"I received $1500 to Cash from Client Job"*
- *"Transfer $300 from City Bank to SBI bank"*
