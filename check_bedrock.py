import boto3
client = boto3.client('bedrock', region_name='us-east-1')
models = client.list_foundation_models(byProvider='Anthropic')
for m in models['modelSummaries']:
    print(m['modelId'])
