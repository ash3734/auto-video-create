import boto3
import json

def load_json_from_s3(bucket: str, key: str) -> list:
    s3 = boto3.client("s3")
    obj = s3.get_object(Bucket=bucket, Key=key)
    return json.loads(obj["Body"].read()) 