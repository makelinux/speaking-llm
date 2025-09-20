# Speaking LLM

A voice-enabled AI assistant that combines speech recognition, text-to-speech, and LLM processing using Llama Stack.

## Features

- **Voice Input**: Real-time speech recognition using Google Speech Recognition
- **Voice Output**: Text-to-speech synthesis using gTTS
- **LLM Integration**: Powered by Llama Stack with configurable models

## Requirements

- **Linux operating system** (tested on Fedora, may work on other distributions)
- Python 3.10+
- Microphone and speakers/headphones
- Internet connection (for Google Speech Recognition and gTTS)
- Llama Stack server

## Installation

### Standard Installation

```bash
pip install .
```

### Development Installation

```bash
pip install -e .
```

After installation, you can run the application from anywhere:

```bash
speaking-llm --help
```

## Usage

### Basic Voice Assistant

```bash
speaking-llm
```

Or if running from source:

```bash
python -m speaking_llm.speaking_llm
```

## Configuration

Edit an optional `agent_config.yaml` file to customize the agent:

```yaml
agent_config:
  model: llama3.2:3b
  toolgroups:
    - mymcp
    - name: builtin::rag/knowledge_search
      args:
        vector_db_ids:
          - your-vector-db-id
  sampling_params:
    strategy:
      type: top_p
      temperature: 1e-9
      top_p: 0
```

Environment variables in config are expanded using `${VAR_NAME}` syntax.

## Architecture

```
Microphone → Speech Recognition → Llama Stack → Text-to-Speech → Speakers
```

### Components

- **Speech Input**: Google Speech Recognition API
- **LLM Backend**: Llama Stack
- **Speech Output**: gTTS (Google Text-to-Speech)

## Voice Commands

- Say **"quit"**, **"exit"**, **"stop"**, **"goodbye"**, **"bye"**, or **"thank you"** to end the session
- Speak naturally - the assistant will process your request and respond with voice

## Files

- `speaking_llm/speaking_llm.py` - Main application
- `speaking_llm/speech_output.py` - Text-to-speech functionality
- `agent_config.yaml` - Optional agent configuration

## Troubleshooting

### Audio Issues

1. **No microphone found**
   - Check microphone permissions
   - Ensure PulseAudio is running: `pulseaudio --check`
   - List audio devices: `pactl list sources short`

2. **Speech recognition errors**
   - Check internet connection
   - Verify microphone is working: `arecord -d 5 test.wav && play -q -v 0.1 test.wav`

3. **Text-to-speech not working**
   - Check internet connection
   - Verify gTTS: `gtts-cli hi | play -q -v 0.1 -t mp3 -`

## Development

Run linting:
```bash
./lint.sh
```

Test echo mode:
```bash
speaking-llm --echo
```
