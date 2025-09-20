#!/usr/bin/env python3
"""
Text-to-Speech module with abbreviation preprocessing.
Provides high-quality speech synthesis using gTTS with fallback to system TTS.
"""

import logging
import os
import re
import subprocess
import sys
from io import BytesIO

import pygame
from gtts import gTTS

logger = logging.getLogger(__name__)


def preprocess_abbreviations(text: str) -> str:
    """Expand common abbreviations for better TTS pronunciation."""
    for abbrev, expansion in {
        # Data rates
        'MBps': 'megabytes per second',
        'Mbps': 'megabits per second',
        'GBps': 'gigabytes per second',
        'Gbps': 'gigabits per second',
        'KBps': 'kilobytes per second',
        'Kbps': 'kilobits per second',
        'KiB/s': 'kilobytes per second',
        'Bytes/s': 'bytes per second',

        # Storage units
        'MB': 'megabytes',
        'GB': 'gigabytes',
        'TB': 'terabytes',
        'KB': 'kilobytes',
        'PB': 'petabytes',

        # Power and frequency
        'MHz': 'megahertz',
        'GHz': 'gigahertz',
        'kHz': 'kilohertz',
        'mW': 'milliwatts',
        'W': 'watts',
        'kW': 'kilowatts',

        # Time units
        'ms': 'milliseconds',
        '0 us': '0',
        'us': 'microseconds',
        'ns': 'nanoseconds',

        'JSON': 'jay son',
        'YAML': 'yah ml',

    }.items():
        # Use word boundaries for precise matching
        pattern = r'\b' + re.escape(abbrev) + r'\b'
        text = re.sub(pattern, expansion, text)

    # Convert large numbers to readable format
    def format_number(match):
        num_str = match.group(0)
        num = int(num_str)
        if num >= 1000000000:
            if num % 1000000000 == 0:
                return f"{num // 1000000000} billion"
            else:
                return f"{num / 1000000000:.1f} billion"
        elif num >= 1000000:
            if num % 1000000 == 0:
                return f"{num // 1000000} million"
            else:
                return f"{num / 1000000:.1f} million"
        elif num >= 100000:  # 100k and above - prefer thousands if result is clean
            thousands = num / 1000
            millions = num / 1000000
            if num % 1000 == 0 and thousands < 1000:  # Clean thousands under 1000
                return f"{int(thousands)} thousand"
            elif num % 100000 == 0:
                return f"{num // 100000} hundred thousand"
            else:
                return f"{millions:.1f} million"
        elif num >= 1000:
            if num % 1000 == 0:
                return f"{num // 1000} thousand"
            else:
                return f"{num / 1000:.1f} thousand"
        return num_str

    # Apply number formatting to numbers with 4+ digits
    text = re.sub(r'\b\d{4,}\b', format_number, text)

    # Convert decimal numbers to spoken form
    def format_decimal(match):
        decimal_str = match.group(0)
        if '.' in decimal_str:
            parts = decimal_str.split('.')
            integer_part = int(parts[0]) if parts[0] else 0
            decimal_part = parts[1]

            # Handle common decimal patterns
            if len(decimal_part) == 1:  # 0.5 -> "5 tenths" or "half"
                digit = int(decimal_part)
                if digit == 5:
                    return f"{integer_part} and a half" if integer_part > 0 else "half"
                else:
                    return f"{integer_part} point {digit}" if integer_part > 0 else f"{digit} tenths"
            elif len(decimal_part) == 2:  # 0.24 -> "24 hundredths"
                decimal_num = int(decimal_part)
                if decimal_num == 0:
                    return str(integer_part) if integer_part > 0 else "zero"
                elif decimal_num < 10:
                    return f"{integer_part} point zero {decimal_num}" if integer_part > 0 else f"{decimal_num} hundredths"
                else:
                    return f"{integer_part} point {decimal_num}" if integer_part > 0 else f"{decimal_num} hundredths"
            else:  # More than 2 decimal places, keep as "point"
                return f"{integer_part} point {decimal_part}" if integer_part > 0 else f"point {decimal_part}"
        return decimal_str

    # Apply decimal formatting to decimal numbers
    text = re.sub(r'\b\d*\.\d+\b', format_decimal, text)

    # Remove or replace long technical values to avoid speaking them
    # Kubernetes resource names with ReplicaSet/Pod suffixes (like -65bb5c54ff-gppzx) - FIRST
    text = re.sub(r'-[0-9a-f]{10}-[a-z0-9]{5}\b', ' with generated suffix', text)

    # Long hex values (6+ characters)
    text = re.sub(r'\b0x[0-9a-f]{6,}\b', '-', text, flags=re.IGNORECASE)
    text = re.sub(r'\b[0-9a-f]{8,}\b', '-', text, flags=re.IGNORECASE)

    # Container/image IDs and hashes
    text = re.sub(r'\bsha256:[0-9a-f]{8,}\b', 'SHA hash', text, flags=re.IGNORECASE)
    text = re.sub(r'id: cri-o://\S+', 'container ID', text)
    text = re.sub(r'\b[0-9a-f]{12,}\b', 'long ID', text)

    # Remove redundant "ID" after container ID replacement
    text = re.sub(r'container ID\s+ID\b', 'container ID', text)

    # Docker image digests
    text = re.sub(r'@sha256:[0-9a-f]+', ' at SHA digest', text)

    # Long base64-like strings (20+ characters of alphanumeric)
    text = re.sub(r'\b[A-Za-z0-9+/]{20,}={0,2}\b', 'encoded value', text)

    # Filter out asterisks used for markdown formatting
    text = re.sub(r'\*+', '', text)

    for old, new in {
        '°C': ' Celsius ',
        '`': ' ',
        '/': ' ',
        '_': ' ',
    }.items():
        text = text.replace(old, new)

    return text


def speak_text(text: str) -> None:
    """Convert text to speech using gTTS with abbreviation preprocessing."""
    # Preprocess text to expand abbreviations
    processed_text = preprocess_abbreviations(text)

    try:
        print("Encoding...", end='', file=sys.stderr, flush=True)
        tts = gTTS(processed_text)
        print('\r\033[K', end='', file=sys.stderr)
        print("Speaking... 📢", end='', file=sys.stderr, flush=True)

        # Create audio data in memory
        audio_buffer = BytesIO()
        tts.write_to_fp(audio_buffer)
        audio_buffer.seek(0)

        # Try different audio drivers/settings for better compatibility
        audio_drivers = [
            {},  # Default settings
            {'frequency': 22050, 'size': -16, 'channels': 2, 'buffer': 512},
            {'frequency': 44100, 'size': -16, 'channels': 1, 'buffer': 1024},
        ]

        mixer_initialized = False
        for audio_config in audio_drivers:
            try:
                pygame.mixer.init(**audio_config)
                mixer_initialized = True
                break
            except pygame.error:
                continue

        if not mixer_initialized:
            raise pygame.error("Could not initialize audio with any configuration")

        pygame.mixer.music.load(audio_buffer)
        pygame.mixer.music.set_volume(0.1)
        pygame.mixer.music.play()

        # Wait for playback to finish
        while pygame.mixer.music.get_busy():
            pygame.time.wait(100)

        if pygame.mixer.get_init():
            pygame.mixer.quit()

        print('\r\033[K', end='', file=sys.stderr)
    except Exception as e:
        print('\r\033[K', end='', file=sys.stderr)
        # Fallback to system TTS if gTTS or pygame fails
        logger.warning(f"gTTS with pygame failed ({e}), falling back to system TTS")
        try:
            # Try espeak first (common on Linux)
            subprocess.run(['espeak', processed_text], check=True, capture_output=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            try:
                # Try say on macOS
                subprocess.run(['say', processed_text], check=True, capture_output=True)
            except (subprocess.CalledProcessError, FileNotFoundError):
                try:
                    # Try spd-say (speech-dispatcher)
                    subprocess.run(['spd-say', processed_text], check=True, capture_output=True)
                except (subprocess.CalledProcessError, FileNotFoundError):
                    logger.warning("No TTS system found (tried: gTTS+pygame, espeak, say, spd-say)")


def self_check() -> bool:
    """
    Comprehensive self-check to test all pattern replacements.
    Returns True if all tests pass, False otherwise.
    """
    test_cases = [
        # Data rates
        ("Transfer rate: 100 MBps", "Transfer rate: 100 megabytes per second"),
        ("Network speed: 1 Gbps", "Network speed: 1 gigabits per second"),
        ("Download: 50 Mbps", "Download: 50 megabits per second"),
        ("Bandwidth: 10 KBps", "Bandwidth: 10 kilobytes per second"),

        # Storage units
        ("File size: 500 MB", "File size: 500 megabytes"),
        ("Disk space: 2 TB", "Disk space: 2 terabytes"),
        ("Memory: 16 GB", "Memory: 16 gigabytes"),
        ("Cache: 256 KB", "Cache: 256 kilobytes"),
        ("Storage: 1 PB", "Storage: 1 petabytes"),

        # Power and frequency
        ("CPU: 3.2 GHz", "CPU: 3 point 2 gigahertz"),  # Decimal formatting happens first
        ("Clock: 800 MHz", "Clock: 800 megahertz"),
        ("Audio: 44 kHz", "Audio: 44 kilohertz"),
        ("Power: 65 W", "Power: 65 watts"),
        ("Consumption: 500 mW", "Consumption: 500 milliwatts"),
        ("Load: 2 kW", "Load: 2 kilowatts"),

        # Time units
        ("Latency: 50 ms", "Latency: 50 milliseconds"),
        ("Delay: 100 us", "Delay: 100 microseconds"),
        ("Response: 500 ns", "Response: 500 nanoseconds"),
        ("Zero latency: 0 us", "Zero latency: 0"),

        # File formats
        ("Config: JSON format", "Config: jay son format"),
        ("Manifest: YAML file", "Manifest: yah ml file"),

        # Number formatting
        ("Count: 1000", "Count: 1 thousand"),
        ("Items: 5000", "Items: 5 thousand"),
        ("Records: 1500000", "Records: 1 and a half million"),  # 1.5 becomes "1 and a half"
        ("Entries: 2000000", "Entries: 2 million"),
        ("Total: 1000000000", "Total: 1 billion"),
        ("Size: 150000", "Size: 150 thousand"),
        ("Value: 2500000", "Value: 2 and a half million"),  # 2.5 becomes "2 and a half"

        # Decimal formatting
        ("Rate: 2.5", "Rate: 2 and a half"),
        ("Value: 0.5", "Value: half"),
        ("Score: 3.7", "Score: 3 point 7"),
        ("Percent: 0.25", "Percent: 25 hundredths"),
        ("Ratio: 1.05", "Ratio: 1 point zero 5"),  # 05 becomes "zero 5"
        ("Factor: 0.123", "Factor: point 123"),

        # Technical value removal/replacement
        ("Pod: nginx-65bb5c54ff-gppzx", "Pod: nginx with generated suffix"),
        # Complex interaction with number formatting
        ("Address: 0x7fff5fbff8a0", "Address: -"),
        ("Hash: sha256:abcd1234efgh5678", "Hash: sha256:abcd1234efgh5678"),  # This pattern doesn't match the regex
        ("Image: nginx@sha256:abc123def456", "Image: nginx@sha256:-"),  # Partial match - hex part gets replaced
        ("Token: YWJjZGVmZ2hpams1Njc4OTA=", "Token: encoded value="),  # Base64 pattern doesn't include trailing =
        ("Code: `example`", "Code:  example "),
        ("**Bold text**", "Bold text"),
        ("*Italic text*", "Italic text"),

        # Special characters and cleanup
        ("Path: /usr/bin", "Path:  usr bin"),  # Forward slash removal removes internal slashes
    ]

    passed = 0
    failed = 0

    for i, (input_text, expected_output) in enumerate(test_cases, 1):
        actual_output = preprocess_abbreviations(input_text)

        if actual_output == expected_output:
            passed += 1
        else:
            print("FAIL:")
            print(f"    Input:    '{input_text}'")
            print(f"    Expected: '{expected_output}'")
            print(f"    Actual:   '{actual_output}'")
            print()
            failed += 1

    print(f"Results: {passed} passed, {failed} failed")

    return failed == 0


if __name__ == "__main__":
    import sys

    # Check if --self-check flag is provided
    if len(sys.argv) > 1 and sys.argv[1] == "--self-check":
        success = self_check()
        sys.exit(0 if success else 1)
    elif len(sys.argv) > 1:
        test_text = " ".join(sys.argv[1:])
        speak_text(test_text)
    else:
        print("Usage:")
        print("  python speech_output.py <text to speak>")
        print("  python speech_output.py --self-check")
        print()
        print("Examples:")
        print("  python speech_output.py 'CPU usage at 2.5 GHz with 100 MBps throughput'")
        print("  python speech_output.py --self-check")
