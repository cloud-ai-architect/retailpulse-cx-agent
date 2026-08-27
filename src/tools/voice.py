"""Voice tools — Amazon Transcribe (STT) and Amazon Polly (TTS)."""

from __future__ import annotations

import json
import time
from typing import Any

import boto3


def transcribe_audio(audio_s3_uri: str, language: str = "en-IN") -> dict[str, Any]:
    """Start a Transcribe job and wait for the result.

    audio_s3_uri: s3://bucket/key for the audio file
    language: BCP-47 language code (en-IN, hi-IN, etc.)
    """
    transcribe = boto3.client("transcribe", region_name="ap-south-1")
    bucket, key = audio_s3_uri.replace("s3://", "").split("/", 1)
    job_name = f"retailpulse-{int(time.time())}"

    transcribe.start_transcription_job(
        TranscriptionJobName=job_name,
        LanguageCode=language,
        MediaFormat="wav",  # or detect from extension
        Media={"MediaFileUri": audio_s3_uri},
        OutputBucketName=bucket,
        OutputKey=f"transcripts/{job_name}.json",
    )

    # Wait for completion
    while True:
        status = transcribe.get_transcription_job(TranscriptionJobName=job_name)
        if status["TranscriptionJob"]["TranscriptionJobStatus"] in ("COMPLETED", "FAILED"):
            break
        time.sleep(2)

    if status["TranscriptionJob"]["TranscriptionJobStatus"] == "FAILED":
        return {"error": status["TranscriptionJob"].get("FailureReason", "Unknown")}

    # Read transcript from S3
    s3 = boto3.client("s3", region_name="ap-south-1")
    obj = s3.get_object(Bucket=bucket, Key=f"transcripts/{job_name}.json")
    data = json.loads(obj["Body"].read().decode("utf-8"))
    return {"transcript": data.get("results", {}).get("transcripts", [{}])[0].get("transcript", "")}


def synthesize_speech(text: str, voice: str = "Kajal", output_s3_bucket: str = "retailpulse-dev-ui") -> str:
    """Synthesize speech with Polly and upload to S3.

    Returns: s3 URI of the audio file
    """
    polly = boto3.client("polly", region_name="ap-south-1")
    s3 = boto3.client("s3", region_name="ap-south-1")

    response = polly.synthesize_speech(
        Text=text,
        OutputFormat="mp3",
        VoiceId=voice,  # "Kajal" or "Aditi" for Indian English
        Engine="neural",
    )

    key = f"audio/{int(time.time())}-{hash(text) & 0xffffffff}.mp3"
    s3.put_object(
        Bucket=output_s3_bucket,
        Key=key,
        Body=response["AudioStream"].read(),
        ContentType="audio/mpeg",
    )
    return f"s3://{output_s3_bucket}/{key}"
