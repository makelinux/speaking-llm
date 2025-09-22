#!/usr/bin/env python3

from llama_stack_client.lib.agents.agent import AsyncAgent
from llama_stack_client import AsyncLlamaStackClient
from llama_stack.core.library_client import AsyncLlamaStackAsLibraryClient
import yaml
from io import StringIO
from contextlib import redirect_stdout
import warnings
import sys
import signal
import logging
import json
import asyncio
import argparse
import os

os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = '1'
warnings.filterwarnings("ignore", category=UserWarning, module="pygame")
from .speech_output import speak_text


args = None
logger = None
agent = None


async def agent_session():
    global agent
    client = AsyncLlamaStackClient(base_url="http://localhost:8321")
    print('Connecting...', end='', file=sys.stderr, flush=True)
    mods = await client.models.list()
    print('\r\033[K', end='', file=sys.stderr)
    logger.debug(f'Connected to local llama-stack server, Models: {' ' .join([m.identifier for m in mods])}')

    config = {"model": "gemini/gemini-2.5-flash", 'instructions': 'You are speaking assistant.'}
    try:
        with open("agent_config.yaml", 'r') as f:
            config = yaml.safe_load(f)
        if config and 'agent_config' in config:
            config = config['agent_config']
    except Exception as e:
        logger.debug(f"Warning: Could not load agent_config.yaml: {e}", file=sys.stderr)

    agent = AsyncAgent(client, **config)

    return await agent.create_session("speaking_llm")


async def turn(prompt_text: str, session_id: str) -> None:
    print("Thinking... ⚙️", end='', file=sys.stderr, flush=True)
    while True:
        r = await agent.create_turn([{"role": "user", "content": prompt_text}], session_id, stream=False)
        if r.output_message.content:
            print('\r\033[K', end='', file=sys.stderr)
            return r
        logger.warning("Empty response")


def print_input(text):
    """Print input text with appropriate formatting."""
    print(f"\033[3m{text}\033[0m\n")


async def _process_single_prompt(prompt_text: str, session_id: str) -> None:
    print_input(prompt_text)
    r = await turn(prompt_text, session_id)
    print(r.output_message.content, "\n")
    speak_text(r.output_message.content)


def setup_microphone():
    """Initialize microphone with fallback to multiple device indices."""
    import speech_recognition as sr

    microphone_names = sr.Microphone.list_microphone_names()

    mic = None
    for device_idx in [None, 1, 0, 2]:
        try:
            mic = sr.Microphone(device_index=device_idx)

            # Get the actual device name if available
            if device_idx is None:
                device_name = "default"
            elif device_idx < len(microphone_names):
                device_name = f"device {device_idx}: {microphone_names[device_idx]}"
            else:
                device_name = f"device {device_idx}"

            try:
                mic.stream = None
                with mic as test_source:
                    pass
                logger.debug(f"Using microphone: {device_name}")
                return mic
            except Exception:
                mic = None
                continue
        except Exception:
            continue

    return None


async def voice_loop(processor_func, welcome_msg: str):
    """Common voice loop structure for both echo and agent modes."""
    import speech_recognition as sr

    mic = setup_microphone()
    if mic is None:
        print("No working microphone found!", file=sys.stderr)
        return

    r = sr.Recognizer()
    with mic as source:
        print("Calibrating ambient noise...", file=sys.stderr)
        r.adjust_for_ambient_noise(source, duration=1)
        if not args.debug:
            os.system('clear')
        print(welcome_msg, file=sys.stderr)

        while True:
            print("Listening... 🎤", end='', file=sys.stderr, flush=True)
            audio = r.listen(source)
            print('\r\033[K', end='', file=sys.stderr)

            try:
                print("Decoding...", end='', file=sys.stderr, flush=True)
                text = r.recognize_google(audio)
                print('\r\033[K', end='', file=sys.stderr)

                if text.lower() in ['quit', 'exit', 'stop', 'goodbye', 'bye', 'thank you']:
                    print("Goodbye\n")
                    speak_text("Goodbye")
                    break

                await processor_func(text)

            except sr.UnknownValueError:
                print('\r\033[KCould not understand audio.', file=sys.stderr)
            except sr.RequestError as e:
                print(f'\r\033[KSpeech recognition error: {e}', file=sys.stderr)


async def echo_processor(text: str) -> bool:
    """Process text in echo mode."""
    print_input(text)
    speak_text(text)


async def echo_voice_loop() -> None:
    """Echo mode for testing speech I/O without agent"""
    await voice_loop(echo_processor, "Echo mode: Say something and I'll repeat it back. Say 'quit' to exit.")


async def agent_processor(text: str) -> bool:
    """Process text with agent."""
    await _process_single_prompt(text, agent_processor.session_id)


async def main():
    # Parse command line arguments
    global args, logger

    parser = argparse.ArgumentParser(description="Speaking LLM")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    parser.add_argument("--echo", action="store_true", help="Echo mode: test speech I/O without LLM")
    parser.add_argument("--hi", action="store_true", help="Send 'Hi' to LLM to check configuration")
    args = parser.parse_args()

    logger = logging.getLogger(__name__)
    if args.debug:
        logger.setLevel(logging.DEBUG)

    if args.echo:
        await echo_voice_loop()
    else:
        session_id = await agent_session()
        if args.hi:
            await _process_single_prompt("hi", session_id)
            await _process_single_prompt("hi", session_id)
            exit(0)
            agent_processor.session_id = session_id
            await agent_processor("hi")
            try:
                await agent_processor("hi")
            except Exception:
                pass
            await agent_processor("hi")
        else:
            agent_processor.session_id = session_id
            await voice_loop(agent_processor, "Say 'thank you', 'exit' or 'quit' to stop.")


def cli_main():
    """Entry point for console script."""
    def signal_handler(signum, frame):
        print("\n")
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n")
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    cli_main()
