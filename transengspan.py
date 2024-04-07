import os
from datetime import datetime
import pytube as pt
import whisper
from googletrans import Translator
import html
from google.cloud import texttospeech
import streamlit as st
import zipfile
import subprocess
import time
import json
import re

# Set Google Cloud credentials environment variable
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = 'ttspeech.json'

# Create a unique folder name using timestamp
current_time = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
folder_name = f"transcriptions_{current_time}"


# Streamlit App
st.title("Translate your Youtube Video from English to Spanish")
st.caption("This application will provide the English Video, English Transcription, Spanish Video and Spanish Transcription")
st.divider()
video_url = st.text_input("Enter YouTube Video URL:")
download_button = st.button("Translate Video")
st.balloons()



def timer(func):
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        print(f"Function '{func.__name__}' took {end_time - start_time} seconds to execute.")
        return result
    return wrapper


@timer
def download_video(video_url):
    os.makedirs(folder_name, exist_ok=True)  # Create the folder if it doesn't exist
    try:
        yt = pt.YouTube(video_url)
        stream = yt.streams.filter(only_audio=True).first()
        stream.download(filename=f"{folder_name}/english_audio.mp3") # Download Audio
        stream = yt.streams.first()  # Select highest resolution
        file_path = stream.download(output_path=folder_name)
        # Renaming the file
        new_file_name = "downloadedEnglishVideo.mp4"  # Enter the new name for the video file
        new_file_path = os.path.join(folder_name, new_file_name)
        os.rename(file_path, new_file_path)

        
        return folder_name
    except Exception as e:
        st.error(f"Error downloading video: {e}")


output_filename = f"{folder_name}/english_transcription.txt"




def transcribe(folder_name):
    audio_file_path = f"{folder_name}/english_audio.mp3"
    
    # Check if the file is too large (example threshold: 500MB)
    if os.path.getsize(audio_file_path) > 500 * 1024 * 1024:
        print("Warning: Large file detected. Transcription may take longer.")
    
    try:
        # Transcribe the downloaded audio
        model = whisper.load_model("base")
        result = model.transcribe(audio_file_path, fp16=False)
        
        # Handle the transcription result
        if result is not None:
            output_filename = f"{folder_name}/english_transcription.txt"
            with open(output_filename, "w") as txt_file:
                for segment in result["segments"]:
                    text = segment["text"]
                    txt_file.write(text + "\n")
            print(f"Transcription written to: {output_filename}")
        else:
            print("Error: Transcription result is None.")
    except Exception as e:
        print(f"An error occurred during transcription: {e}")




from google.cloud import translate_v2 as translate

def translate_text_with_google(text, target='es'):
    translate_client = translate.Client()
    
    # Text can also be a sequence of strings, in which case this method
    # will return a sequence of results for each text.
    result = translate_client.translate(text, target_language=target)

    # print(u"Text: {}".format(result['input']))
    # print(u"Translation: {}".format(result['translatedText']))
    return result['translatedText']



# Function to translate text from English to Spanish

def translate_text(text):
    translator = Translator()
    translated = translator.translate(text, src='en', dest='es')
    return translated.text

# Function to translate text file
@timer
def translate_txt(input_file, output_file):
    with open(input_file, 'r', encoding='utf-8') as file:
        text = file.read()
    time.sleep(20)
    print("ready to translate")
    translated_text = translate_text_with_google(text)
    with open(output_file, 'w', encoding='utf-8') as file:
        file.write(translated_text)

# [END tts_ssml_address_ssml]


# [split text if they are large]
import re

# def split_text(text, max_chunk_size=4000):
#     """
#     Splits the text into chunks, trying to split at sentence endings.
#     Each chunk size is kept below max_chunk_size.
#     """
#     print(translate_text)
#     # Ensure text is a string
#     if not isinstance(text, str):
#         raise ValueError("Text must be a string")

#     # Use regex to find sentence endings; adjust if needed
#     sentences = re.split(r'(?<=[.!?]) +', text)
#     chunks = []
#     current_chunk = sentences[0]

#     for sentence in sentences[1:]:
#         # Check if adding the next sentence would exceed the max chunk size
#         if len(current_chunk) + len(sentence) <= max_chunk_size:
#             current_chunk += " " + sentence
#         else:
#             chunks.append(current_chunk)
#             current_chunk = sentence
#     chunks.append(current_chunk)  # Don't forget to add the last chunk

#     return chunks

def split_text_by_byte_limit(text, max_byte_size=1500):
    """
    Splits the text into chunks, each not exceeding the specified byte limit.
    Tries to split at sentence ends while respecting the byte limit.
    """
    if not text:  # Check for empty or None input
        return []  # Return an empty list to indicate no chunks

    sentences = re.split(r'(?<=[.!?]) +', text)
    chunks = []
    current_chunk = ""

    for sentence in sentences:
        temp_chunk = f"{current_chunk} {sentence}".strip()
        if len(temp_chunk.encode('utf-8')) <= max_byte_size:
            current_chunk = temp_chunk
        else:
            if current_chunk:  # Add the current chunk if it's not empty
                chunks.append(current_chunk)
                current_chunk = sentence
            else:
                # Handle the case where a single sentence exceeds the max_byte_size
                # Here, you might need a strategy for further splitting
                # For now, we'll add it directly, but you may want to handle this differently
                chunks.append(sentence)
                current_chunk = ""  # Reset current_chunk for the next iteration

    if current_chunk:  # Don't forget to add the last chunk
        chunks.append(current_chunk)

    return chunks



#convert text to SSML


@timer
def text_to_ssml(text, rate="medium", pitch="+0st"):
    """
    Converts a chunk of text to SSML, adding breaks and prosody tags around sentences.
    Args:
        text (str): The input text to convert to SSML.
        rate (str): The rate of speech (e.g., "slow", "medium", "fast", or a percentage).
        pitch (str): The pitch adjustment (e.g., "+0st" for no change, "+10st" for higher pitch).
    Returns:
        str: The SSML representation of the input text.
    """
    # Escape HTML special characters and split by sentences to add breaks
    escaped_text = html.escape(text)
    sentences = re.split(r'([.!?])', escaped_text)  # Keep punctuation

    ssml_parts = ['<speak>']
    for i in range(0, len(sentences), 2):
        sentence = sentences[i].strip()
        if i + 1 < len(sentences):
            punctuation = sentences[i + 1]
        else:
            punctuation = ''
        if sentence or punctuation:
            # Wrap each sentence with prosody tags
            ssml_parts.append(f"<prosody rate='{rate}' pitch='{pitch}'>{sentence}{punctuation}</prosody><break time='500ms'/>")
    ssml_parts.append('</speak>')



    return "\n".join(ssml_parts)



    
def synthesize_text(ssml_chunk):
    print(ssml_chunk)
    # """
    # Synthesizes speech from the input string of SSML.
    # """
    client = texttospeech.TextToSpeechClient()
    # Ensure this uses SSML by specifying the ssml parameter
    input_text = texttospeech.SynthesisInput(ssml=ssml_chunk)
    voice = texttospeech.VoiceSelectionParams(
        language_code='es-ES',  # Adjust the language code as necessary
        ssml_gender=texttospeech.SsmlVoiceGender.MALE)
    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.MP3)
    
    response = client.synthesize_speech(input=input_text, voice=voice, audio_config=audio_config)
    return response.audio_content




def combine_audio_files(folder_name, number_of_chunks):
    # Create a list file for ffmpeg
    with open(f'{folder_name}/list.txt', 'w') as f:
        for i in range(number_of_chunks):
            f.write(f"file 'output_chunk_{i}.mp3'\n")

    # Use ffmpeg to concatenate the audio files
    subprocess.run(['ffmpeg', '-f', 'concat', '-safe', '0', '-i', f'{folder_name}/list.txt', 
                    '-c', 'copy', f'{folder_name}/translated.mp3'], check=True)

    # Cleanup: Remove chunk files and list.txt if desired
    # for i in range(number_of_chunks):
    #     os.remove(f'{folder_name}/output_chunk_{i}.mp3')
    # os.remove(f'{folder_name}/list.txt')


if download_button:
    with st.spinner('We are translating your video to spanish...'):
        
        video_folder_path = download_video(video_url)
        time.sleep(10)
        print("video has been downloaded")
        st.write("Your video has been downloaded")
        transcribe(folder_name=folder_name)
        time.sleep(10)
        print("video has been transcribed to english")
        
        # Translate text file
        output_file = f"{folder_name}/spanish_transcription.txt"
    # Input and output file paths
        input_file = output_filename
        # Specify the output filename
        
        print('here is the output file', output_file)
        time.sleep(5)
        translate_txt(input_file, output_file)
        time.sleep(5)
        print("video has been translated to spanish")
        st.write("Your video is currently been translated to spanish ")
        # plaintext = output_file
        time.sleep(5)

        # Read the translated text from output_file
        with open(output_file, 'r', encoding='utf-8') as file:
            translated_text = file.read()

        ssml_chunks = [text_to_ssml(chunk) for chunk in split_text_by_byte_limit(translated_text)]
        audio_contents = [synthesize_text(chunk) for chunk in ssml_chunks]

        # Example of saving each audio chunk to a separate file
        for i, audio_content in enumerate(audio_contents):
            print("breakdown")
            with open(f"{folder_name}/output_chunk_{i}.mp3", 'wb') as audio_file:
                audio_file.write(audio_content)

        
        from pydub import AudioSegment

        combined = AudioSegment.empty()
        # for i, audio_content in enumerate(audio_contents):
        #     print("combine")
        #     segment = AudioSegment.from_file(f"{folder_name}/output_chunk_{i}.mp3", format="mp3")
        #     combined += segment

        for i in range(len(audio_contents)):
            chunk_path = f"{folder_name}/output_chunk_{i}.mp3"
            print("combine")
            segment = AudioSegment.from_file(chunk_path, format="mp3")
            combined += segment
            # Remove the chunk file after it's been added to the combined audio
            os.remove(chunk_path)

        combined.export(f"{folder_name}/translated.mp3", format="mp3")

        # Path to your video and audio files
        import subprocess

        # Path to your video and audio files
        video_file = f"{folder_name}/downloadedEnglishVideo.mp4"
        new_audio_file = f"{folder_name}/translated.mp3"  # Change this to the correct audio file name
        output_video_file = f"{folder_name}/spanish_video.mp4"

        

        # FFmpeg command to remove existing audio and add new audio
        ffmpeg_cmd = f"ffmpeg -i {video_file} -i {new_audio_file} -c:v copy -map 0:v:0? -map 1:a:0 -c:a aac -strict experimental {output_video_file}"

        # Execute FFmpeg command
        subprocess.call(ffmpeg_cmd, shell=True)
    st.balloons()


    st.success(f"Video downloaded successfully to folder {folder_name}")
    if video_folder_path:
        # Zip the folder
        zip_file_path = f"{os.path.basename(video_folder_path)}.zip"
        with zipfile.ZipFile(zip_file_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(video_folder_path):
                for file in files:
                    zipf.write(os.path.join(root, file), os.path.relpath(os.path.join(root, file), video_folder_path))

        # st.markdown(f"Download your video files [here](/{zip_file_path}), right-click the link and choose 'Save link as...' to download.")
        with open(zip_file_path, 'rb') as f:
            st.download_button(f"Download your video files by click here", f.read(), file_name="Video.zip")
    

