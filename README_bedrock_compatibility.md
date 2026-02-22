# Bedrock Model Compatibility Matrix Generator

This script dynamically discovers all available Amazon Bedrock foundation models from both `bedrock-runtime` and `bedrock-mantle` services, tests their compatibility across different inference profiles and API endpoints, and generates a comprehensive CSV compatibility matrix.

## Features

- **Automatic Model Discovery**: Fetches latest models from both bedrock-runtime and bedrock-mantle services
- **Inference Profile Detection**: Discovers and categorizes inference profiles (in-region, regional cross-region, global cross-region)
- **Multi-API Testing**: Tests 4 different APIs for each model:
  - `invoke_model` API (bedrock-runtime)
  - `converse` API (bedrock-runtime)
  - `chat_completions` API (OpenAI-compatible via bedrock-runtime)
  - `responses` API (OpenAI-compatible via bedrock-mantle)
- **CSV Output**: Generates a compatibility matrix with ✓/✗ markers
- **Error Logging**: Detailed error log for debugging

## Requirements

```bash
pip install boto3 openai httpx
```

Or use the provided requirements file:

```bash
pip install -r requirements_compatibility_matrix.txt
```

## Prerequisites

- AWS credentials configured (via `aws configure` or environment variables)
- Appropriate IAM permissions for:
  - `bedrock:ListFoundationModels`
  - `bedrock:ListInferenceProfiles`
  - `bedrock-runtime:InvokeModel`
  - `bedrock-runtime:Converse`
  - `bedrock-mantle:*` (for mantle operations)

## Usage

### Basic Usage

Test all available models:

```bash
python bedrock_compatibility_matrix.py
```

### Quick Testing

Test only the first N models (useful for quick validation):

```bash
python bedrock_compatibility_matrix.py --limit 10
```

### Custom Output

Specify custom output filenames:

```bash
python bedrock_compatibility_matrix.py --output my_results.csv --error-log my_errors.log
```

### Command-Line Options

- `--output`: Output CSV filename (default: `bedrock_compatibility_matrix.csv`)
- `--limit`: Limit number of models to test (default: all models)
- `--error-log`: Error log filename (default: `bedrock_errors.log`)

## Output Format

### CSV File

The generated CSV contains the following columns:

| Column | Description |
|--------|-------------|
| Model | Model ID |
| Service | Service name (bedrock-runtime or bedrock-mantle) |
| Profile_Type | Inference profile type (in-region, regional-cross-region, global-cross-region) |
| Invoke_API | ✓ if supported, ✗ if not |
| Converse_API | ✓ if supported, ✗ if not |
| ChatCompletions_API | ✓ if supported, ✗ if not |
| Responses_API | ✓ if supported, ✗ if not |

### Example Output

```csv
Model,Service,Profile_Type,Invoke_API,Converse_API,ChatCompletions_API,Responses_API
nvidia.nemotron-nano-12b-v2,bedrock-runtime,in-region,✓,✓,✗,✗
qwen.qwen3-coder-next,bedrock-runtime,in-region,✓,✓,✗,✗
openai.gpt-oss-120b,bedrock-mantle,in-region,✗,✗,✗,✓
```

## Region Configuration

The script is configured to test models in `us-east-1` by default. To change the region, modify the `REGION` constant in the script:

```python
REGION = 'us-west-2'  # Change to your preferred region
```

## Notes

- The script makes actual inference calls to verify API compatibility
- Testing all models can take significant time (several minutes to hours depending on the number of models)
- Some models may require specific IAM permissions or model access grants
- The script uses a minimal test prompt ("Hi") with low token limits to minimize costs
- Timeout is set to 30 seconds per API call

## Troubleshooting

### Authentication Errors

Ensure your AWS credentials are properly configured:

```bash
aws configure
```

### Permission Errors

Verify you have the necessary IAM permissions for Bedrock operations.

### Model Access Errors

Some models may require explicit access grants through the AWS Bedrock console.

## Summary Statistics

The script provides summary statistics at the end:

- Total models tested
- Total API combinations tested
- Number of supported combinations
- Overall success rate

Example:

```
=== Summary ===
Total models tested: 164
Total API combinations: 656
Supported combinations: 328
Success rate: 50.0%

Results saved to: bedrock_compatibility_matrix.csv
Error log saved to: bedrock_errors.log
```
