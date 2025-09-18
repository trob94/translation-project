import os
import boto3
import time
import json

# Setup
bucket = os.environ['S3_BUCKET']
environment = os.environ.get('ENVIRONMENT', 'beta')

s3 = boto3.client('s3')
transcribe = boto3.client('transcribe')
translate = boto3.client('translate')
polly = boto3.client('polly')

# Find MP3 files
import glob
mp3_files = glob.glob("audio_inputs/*.mp3")

if not mp3_files:
    print("No MP3 files found!")
    exit()

for mp3_file in mp3_files:
    filename = mp3_file.split('/')[-1].replace('.mp3', '')
    print(f"Processing {filename}...")
    
    # 1. Upload MP3 to S3
    s3.upload_file(mp3_file, bucket, f"temp/{filename}.mp3")
    print("Uploaded")
    
    # 2. Transcribe (convert speech to text)
    job_name = f"job-{filename}-{int(time.time())}"
    transcribe.start_transcription_job(
        TranscriptionJobName=job_name,
        Media={'MediaFileUri': f's3://{bucket}/temp/{filename}.mp3'},
        MediaFormat='mp3',
        LanguageCode='en-US'
    )
    
    # Wait for transcription
    while True:
        job = transcribe.get_transcription_job(TranscriptionJobName=job_name)
        if job['TranscriptionJob']['TranscriptionJobStatus'] == 'COMPLETED':
            break
        print("⏳ Waiting...")
        time.sleep(15)
    
    # Get transcript
    import requests
    url = job['TranscriptionJob']['Transcript']['TranscriptFileUri']
    response = requests.get(url)
    transcript = json.loads(response.text)['results']['transcripts'][0]['transcript']
    print("Transcribed")
    
    # 3. Save transcript
    s3.put_object(
        Bucket=bucket,
        Key=f"{environment}/transcripts/{filename}.txt",
        Body=transcript
    )
    
    # 4. Translate to Spanish
    translated = translate.translate_text(
        Text=transcript,
        SourceLanguageCode='en',
        TargetLanguageCode='es'
    )['TranslatedText']
    print("Translated")
    
    # 5. Save translation
    s3.put_object(
        Bucket=bucket,
        Key=f"{environment}/translations/{filename}_es.txt",
        Body=translated
    )
    
    # 6. Convert to speech
    speech = polly.synthesize_speech(
        Text=translated,
        OutputFormat='mp3',
        VoiceId='Joanna'
    )
    
    # Save and upload audio
    with open(f'/tmp/{filename}_es.mp3', 'wb') as f:
        f.write(speech['AudioStream'].read())
    
    s3.upload_file(f'/tmp/{filename}_es.mp3', bucket, f"{environment}/audio_outputs/{filename}_es.mp3")
    print("Done!")
    
    # Cleanup
    os.remove(f'/tmp/{filename}_es.mp3')
    s3.delete_object(Bucket=bucket, Key=f"temp/{filename}.mp3")

print("All files processed!")
