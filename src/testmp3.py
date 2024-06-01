import logging
from io import BytesIO
from mutagen.mp3 import MP3

from replaygain.main import process_replaygain

logging.basicConfig(level=logging.DEBUG)

def process_test_mp3():
    try:
        input_file_path = 'test.mp3'
        output_file_path = 'post-test.mp3'

        # Read the content of 'test.mp3' file
        with open(input_file_path, 'rb') as infile:
            file_content = infile.read()

        # Ensure it's not empty
        if len(file_content) < 4:
            raise ValueError("The input file is too small to be a valid MP3 file.")

        # Check if Mutagen can load the MP3 file
        logging.debug(f"Testing if Mutagen can load the file: {input_file_path}")
        try:
            audio = MP3(BytesIO(file_content))
            logging.info(f"Mutagen loaded the file: {input_file_path}")
        except Exception as audio_load_error:
            logging.error(f"Mutagen failed to load the file: {audio_load_error}")
            raise

        # Process the ReplayGain
        logging.debug(f"Processing ReplayGain for file: {input_file_path}")
        processed_content = process_replaygain(file_content, 'mp3')

        # Write the processed content to 'post-test.mp3'
        with open(output_file_path, 'wb') as outfile:
            outfile.write(processed_content)
        
        logging.info(f"ReplayGain processing complete. Output written to '{output_file_path}'")

    except Exception as e:
        logging.error(f"Error processing ReplayGain: {e}")

# Run the test process
if __name__ == "__main__":
    process_test_mp3()
