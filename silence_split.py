import os
import math
import argparse
import ffmpeg
import json
import re
import logging

# Configure logging to both console and file
log_file = 'audio_processing.log'  # Specify the log file name
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),  # Log to console
        logging.FileHandler(log_file)  # Log to file
    ]
)

# Function to probe the original MKV file and detect audio codec
def get_audio_codec(mkv_file: str) -> tuple:
    probe = ffmpeg.probe(mkv_file)
    audio_streams = [stream for stream in probe['streams'] if stream['codec_type'] == 'audio']
    if audio_streams:
        codec_name = audio_streams[0]['codec_name']
        container_format = probe['format']['format_name'].split(',')[0]
        logging.info(f"Detected audio codec: {codec_name}, container format: {container_format}")
        return codec_name, container_format
    else:
        raise ValueError(f"No audio stream found in {mkv_file}")

# Function to extract audio chunks (used only for silence detection)
def extract_audio_chunks(mkv_file: str, output_dir: str, chunk_duration: int = 2700) -> list:
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # Get video info (to extract duration)
    probe = ffmpeg.probe(mkv_file)
    duration = float(probe['format']['duration'])

    # Number of chunks needed
    num_chunks = math.ceil(duration / chunk_duration)

    chunk_files = []

    # Split the mkv file into chunks of given duration (for silence detection)
    for i in range(num_chunks):
        start_time = i * chunk_duration
        output_chunk = os.path.join(output_dir, f"chunk_{i + 1}.wav")

        # Check if the chunk file already exists
        if os.path.exists(output_chunk):
            logging.info(f"Chunk {output_chunk} already exists, skipping conversion.")
        else:
            logging.info(f"Creating chunk {output_chunk} from {start_time} seconds.")
            # Use ffmpeg-python to split and convert to wav, ignoring video stream
            (
                ffmpeg
                .input(mkv_file, ss=start_time, t=chunk_duration)
                .output(output_chunk, format='wav', acodec='pcm_s16le', vn=None)  # Force no video stream
                .run(overwrite_output=True)
            )

        chunk_files.append(output_chunk)

    return chunk_files

# Function to detect silences in the given wav file
def detect_silence(wav_file: str, silence_threshold: int = -40, silence_duration: float = 2) -> list:
    # Run ffmpeg's silencedetect filter to detect silences
    output = (
        ffmpeg
        .input(wav_file)
        .filter('silencedetect', noise=f'{silence_threshold}dB', d=silence_duration)
        .output('null', f='null')
        .run(capture_stderr=True, capture_stdout=True)
    )

    stderr_output = output[1].decode('utf-8')
    silences = []

    # Parse ffmpeg output to find silence start and end times
    for line in stderr_output.splitlines():
        if "silence_start" in line:
            start = float(line.split('silence_start: ')[1])
        if "silence_end" in line:
            end = float(line.split('silence_end: ')[1].split(' |')[0])
            silences.append((start, end))

    return silences

# Helper function to sort chunk files by their chunk number
def sort_chunks(chunk_files: list) -> list:
    # Sort based on the number in the chunk filename (e.g., chunk_1.wav -> 1)
    def extract_chunk_number(filename: str) -> int:
        match = re.search(r'chunk_(\d+)', filename)
        return int(match.group(1)) if match else float('inf')

    return sorted(chunk_files, key=extract_chunk_number)

# Function to extract a frame from the middle of a split and save it as a cover image
def extract_middle_frame(mkv_file: str, start_time: float, end_time: float, output_image: str) -> None:
    middle_time = (start_time + end_time) / 2
    logging.info(f"Extracting frame at {middle_time} seconds as cover image.")
    (
        ffmpeg
        .input(mkv_file, ss=middle_time)
        .output(output_image, vframes=1)
        .run(overwrite_output=True)
    )

# Function to split original MKV by silence timestamps loaded from JSON files, and store only audio
def split_original_by_silence(mkv_file: str, output_dir: str, chunk_duration: int, silence_threshold: int) -> None:
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    prev_end = 0  # Start from the beginning of the original file
    split_count = 0
    all_silences = []

    # Load silence points from JSON files for each chunk and sort them by chunk number
    chunk_files = [
        f for f in os.listdir(output_dir)
        if f.endswith(f'_silence_{silence_threshold}.json') and not f.startswith('.')
    ]

    # Sort chunk files by chunk number
    chunk_files = sort_chunks(chunk_files)

    # Get original audio codec
    audio_codec, container_format = get_audio_codec(mkv_file)

    for chunk_file in chunk_files:
        silence_json_path = os.path.join(output_dir, chunk_file)

        # Load the silence points from the JSON file
        logging.info(f"Loading silence data from {silence_json_path}")
        with open(silence_json_path, 'r') as f:
            silences = json.load(f)

        # Adjust silences to original file's time
        chunk_idx = int(chunk_file.split('_')[1]) - 1  # Extract chunk number from filename
        chunk_offset = chunk_idx * chunk_duration
        adjusted_silences = [(start + chunk_offset, end + chunk_offset) for start, end in silences]
        all_silences.extend(adjusted_silences)

    # Split the original file by detected silences, extracting only the audio stream
    for silence in all_silences:
        silence_start, silence_end = silence
        if silence_start - prev_end < 10:  # Consider defining a constant for '10'
            logging.info("Audio segment is too short, skipping.")
            split_count += 1
            prev_end = silence_end
            continue

        # Store the split audio stream in the original audio format
        output_audio = os.path.join(output_dir, f"split_{split_count + 1}.{container_format}")
        output_image = os.path.join(output_dir, f"split_{split_count + 1}.jpg")

        if os.path.exists(output_audio):
            logging.info(f"Split audio {output_audio} already exists, skipping.")
        else:
            logging.info(f"Creating split audio {output_audio} from {prev_end} to {silence_start} seconds.")
            (
                ffmpeg
                .input(mkv_file, ss=prev_end, to=silence_start)
                .output(output_audio, acodec=audio_codec, format=container_format, vn=None)  # Force no video stream
                .run(overwrite_output=True)
            )

        # Extract a frame at the middle of the split as a cover image
        if os.path.exists(output_image):
            logging.info(f"Cover image {output_image} already exists, skipping.")
        else:
            extract_middle_frame(mkv_file, prev_end, silence_start, output_image)

        split_count += 1
        prev_end = silence_end

    # Split the remaining part of the original file after the last silence, and extract only audio
    final_audio = os.path.join(output_dir, f"split_{split_count + 1}.{container_format}")
    final_image = os.path.join(output_dir, f"split_{split_count + 1}.jpg")

    if os.path.exists(final_audio):
        logging.info(f"Final split audio {final_audio} already exists, skipping.")
    else:
        logging.info(f"Creating final split audio {final_audio} from {prev_end} to the end.")
        (
            ffmpeg
            .input(mkv_file, ss=prev_end)
            .output(final_audio, acodec=audio_codec, format=container_format, vn=None)  # Force no video stream
            .run(overwrite_output=True)
        )

    # Extract a frame at the middle of the final split
    if os.path.exists(final_image):
        logging.info(f"Final cover image {final_image} already exists, skipping.")
    else:
        extract_middle_frame(mkv_file, prev_end, float(ffmpeg.probe(mkv_file)['format']['duration']), final_image)

# Main function to process the entire file
def process_mkv_file(mkv_file: str, chunk_duration: int = 2700, silence_threshold: int = -40, silence_duration: float = 2) -> None:
    # Get the base name of the input MKV file for naming the output directory
    base_name = os.path.splitext(os.path.basename(mkv_file))[0]

    # Create an output directory in the same folder as the MKV file
    mkv_dir = os.path.dirname(os.path.abspath(mkv_file))
    output_dir = os.path.join(mkv_dir, base_name)

    logging.info(f"Creating output directory: {output_dir}")

    # Step 1: Extract audio chunks (for silence detection)
    logging.info("Extracting and splitting audio into chunks for silence detection...")
    chunk_files = extract_audio_chunks(mkv_file, output_dir, chunk_duration)

    # Step 2: Detect silence in each chunk
    for chunk_file in chunk_files:
        logging.info(f"Detecting silence in chunk: {chunk_file}")

        # Define cache file for this chunk's silence data (with silence threshold included)
        silence_cache_file = os.path.splitext(chunk_file)[0] + f"_silence_{silence_threshold}.json"

        # Check if silence data already exists for this chunk
        if os.path.exists(silence_cache_file):
            logging.info(f"Using cached silence data for {chunk_file}")
        else:
            # Detect silences in the current chunk
            silences = detect_silence(chunk_file, silence_threshold, silence_duration)

            # Save detected silences to cache (with silence threshold in the filename)
            with open(silence_cache_file, 'w') as f:
                json.dump(silences, f, indent=4)

    # Step 3: Split the original MKV by the adjusted silence timestamps, and save only audio
    logging.info("Splitting the original file by detected silences and saving audio streams...")
    split_original_by_silence(mkv_file, output_dir, chunk_duration, silence_threshold)

    logging.info("Processing completed!")

if __name__ == "__main__":
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="Extract audio from MKV, split by silence, and save the result.")

    parser.add_argument('--mkv_file', type=str, required=True, help='Path to the MKV file.')
    parser.add_argument('--chunk_duration', type=int, default=45 * 60,
                        help='Chunk duration in seconds (default is 45 minutes).')
    parser.add_argument('--silence_threshold', type=int, default=-40,
                        help='Silence threshold in dB (default is -40dB).')
    parser.add_argument('--silence_duration', type=float, default=2,
                        help='Minimum silence duration in seconds (default is 2 seconds).')

    args = parser.parse_args()

    # Call the processing function with the provided arguments
    process_mkv_file(
        args.mkv_file,
        chunk_duration=args.chunk_duration,
        silence_threshold=args.silence_threshold,
        silence_duration=args.silence_duration
    )