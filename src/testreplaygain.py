import logging
from io import BytesIO
from mutagen.mp3 import MP3
from mutagen.flac import FLAC

from replaygain.main import process_replaygain, has_replaygain_metadata

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
        if has_replaygain_metadata(BytesIO(processed_content), 'mp3'):
            logging.info(f"ReplayGain metadata found in the processed content.")
        else:
            logging.error(f"ReplayGain metadata not found in the processed content.")

        # Write the processed content to 'post-test.mp3'
        with open(output_file_path, 'wb') as outfile:
            outfile.write(processed_content)
        
        logging.info(f"ReplayGain processing complete. Output written to '{output_file_path}'")

    except Exception as e:
        logging.error(f"Error processing ReplayGain: {e}")

def process_test_flac():
    try:
        input_file_path = 'test.flac'
        output_file_path = 'post-test.flac'

        # Read the content of 'test.flac' file
        with open(input_file_path, 'rb') as infile:
            file_content = infile.read()

        # Ensure it's not empty
        if len(file_content) < 4:
            raise ValueError("The input file is too small to be a valid flac file.")

        # Check if Mutagen can load the flac file
        logging.debug(f"Testing if Mutagen can load the file: {input_file_path}")
        try:
            audio = FLAC(BytesIO(file_content))
            logging.info(f"Mutagen loaded the file: {input_file_path}")
        except Exception as audio_load_error:
            logging.error(f"Mutagen failed to load the file: {audio_load_error}")
            raise

        # Process the ReplayGain
        logging.debug(f"Processing ReplayGain for file: {input_file_path}")
        processed_content = process_replaygain(file_content, 'flac')
        if has_replaygain_metadata(BytesIO(processed_content), 'flac'):
            logging.info(f"ReplayGain metadata found in the processed content.")
        else:
            logging.error(f"ReplayGain metadata not found in the processed content.")

        # Write the processed content to 'post-test.flac'
        with open(output_file_path, 'wb') as outfile:
            outfile.write(processed_content)
        
        logging.info(f"ReplayGain processing complete. Output written to '{output_file_path}'")

    except Exception as e:
        logging.error(f"Error processing ReplayGain: {e}")

def process_test_opus():
    try:
        input_file_path = 'test.opus'
        output_file_path = 'post-test.opus'

        # Read the content of 'test.opus' file
        with open(input_file_path, 'rb') as infile:
            file_content = infile.read()

        # Ensure it's not empty
        if len(file_content) < 4:
            raise ValueError("The input file is too small to be a valid opus file.")

        # Process the ReplayGain
        logging.debug(f"Processing ReplayGain for file: {input_file_path}")
        processed_content = process_replaygain(file_content, 'opus')
        if has_replaygain_metadata(BytesIO(processed_content), 'opus'):
            logging.info(f"ReplayGain metadata found in the processed content.")
        else:
            logging.error(f"ReplayGain metadata not found in the processed content.")

        # Write the processed content to 'post-test.opus'
        with open(output_file_path, 'wb') as outfile:
            outfile.write(processed_content)
        
        logging.info(f"ReplayGain processing complete. Output written to '{output_file_path}'")

    except Exception as e:
        logging.error(f"Error processing ReplayGain: {e}")

# Run the test process
if __name__ == "__main__":
    process_test_opus()
    process_test_flac()
    process_test_mp3()
