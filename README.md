# Audio Processing Script

## Purpose

The `silence_split.py` script extracts audio from MKV files, detects silence to split it into chunks, and saves each segment with a cover image. This is especially useful for long audio or video files, as it prevents file size limits encountered with WAV formats, which max out at ~4 GB or ~6 hours at CD quality (16-bit, 44.1 kHz, stereo). For large files, this script helps efficiently create manageable, smaller audio tracks.

## Features

- Detects the audio codec of the input MKV file.
- Extracts audio chunks of a specified duration for silence detection.
- Detects silences in the extracted audio chunks.
- Splits the original MKV file into audio segments based on detected silences.
- Saves each audio segment in its original format along with a cover image extracted from the middle of the segment.
- Caches silence detection results to avoid redundant processing.

## Requirements

- Python 3.x
- `ffmpeg` installed on your system (ensure it's available in your system's PATH).
- Required Python packages:
  - `ffmpeg-python`
  - `argparse`
  - `json`
  - `re`
  - `logging`

You can install the required Python packages using pip:

```
pip install ffmpeg-python
```


## Usage

1. **Clone the repository** or download the script file.

2. **Open a terminal** and navigate to the directory where the script is located.

3. **Run the script** using the following command:

   ```bash
   python audio_processing.py --mkv_file <path_to_your_mkv_file> [--chunk_duration <duration_in_seconds>] [--silence_threshold <threshold_in_dB>] [--silence_duration <duration_in_seconds>]
   ```

   - `--mkv_file`: Required. The path to the MKV file you want to process.
   - `--chunk_duration`: Optional. The duration of each audio chunk in seconds (default is 2700 seconds or 45 minutes).
   - `--silence_threshold`: Optional. The silence threshold in dB (default is -40 dB).
   - `--silence_duration`: Optional. The minimum duration of silence in seconds (default is 2 seconds).

### Example

To process a file named `example.mkv` with the default parameters, you would run:

```
python audio_processing.py --mkv_file example.mkv
```


To specify a chunk duration of 10 minutes, you would run:
```
python audio_processing.py --mkv_file example.mkv --chunk_duration 600
```

## Output

The script will create an output directory named after the MKV file (without the extension) in the same folder as the input file. Inside this directory, you will find:

- Split audio files named `split_1.<original_format>`, `split_2.<original_format>`, etc.
- Cover images named `split_1.jpg`, `split_2.jpg`, etc., corresponding to each audio segment.
- A log file named `audio_processing.log` containing detailed logs of the processing steps.