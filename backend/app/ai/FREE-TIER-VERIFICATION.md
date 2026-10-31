# Finish real Gemini verification without enabling billing

The AI implementation and offline tests are complete. A live check still needs a
Gemini project/key, an eligible model and genuine report text. No live call has been
made during development. The following steps do not require committing credentials.

1. Open [Google AI Studio API keys](https://aistudio.google.com/api-keys). Select or
   create your project and key. Confirm its project is labeled **Free Tier** in AI Studio.
   Do not select Set up billing or upgrade. An API key alone does not prove free-tier status.
2. Check [Google's model pricing](https://ai.google.dev/gemini-api/docs/pricing) and select
   an available model whose Free Tier column supports the input types you intend to test.
   Copy its exact model identifier; this project deliberately has no guessed model default.
3. In the PowerShell terminal used to run this module, from the repository root:

```powershell
Set-Location backend/app/ai
$geminiKeyInput = Read-Host 'Paste your Gemini API key locally (hidden)' -AsSecureString
$env:GEMINI_API_KEY = [System.Net.NetworkCredential]::new('', $geminiKeyInput).Password
Remove-Variable geminiKeyInput
$env:GEMINI_MODEL = Read-Host 'Enter the exact free-tier-supported model identifier'
uv run --frozen civicmesh-extract --check-config
```

The key is entered locally with hidden input and stays in the terminal's process environment.
Do not paste it in chat, screenshots, files committed to Git or command-line arguments.
This module does not load .env automatically. The configuration check makes no network
request and prints only whether variables are present; it does not verify billing or the key.

4. Create the ignored private input directory:

```powershell
New-Item -ItemType Directory -Force private-inputs | Out-Null
notepad private-inputs/report.txt
```

Write a short, genuine garbage/water-leak observation in UTF-8, without names, phone numbers,
addresses or other sensitive information. Missing details should stay missing. For the
free tier, consider Google's data-use terms: inputs/outputs may be used to improve products.
Do not invent an operational report or use isolated test fixtures as a real report.

5. Once you have verified the project's Free Tier and the selected model's eligibility:

```powershell
uv run --frozen civicmesh-extract --text-file private-inputs/report.txt --allow-api-call
```

This authorizes **one live extraction request** with no automatic retry. The flag is consent
to an API call; it is not a billing control. A paid project/model can still incur charges.
The CLI cannot determine or change project billing from the API key. If free quota is exhausted
or the model is unavailable, stop and inspect the error; do not enable billing to bypass it.

The older --allow-paid-call flag remains a compatibility alias. Its name never guaranteed
that a charge would occur; --allow-api-call is the preferred, accurate spelling.

6. Check the actual result against your observation: category, summary, language, unknowns,
   and whether unsupported information was invented. Record the model, test input type and
   result privately; do not publish personal report content. Hindi, English, image and audio
   quality each need their own genuine inputs. Do not infer accuracy from a single test.

For photo/audio verification, use real backend evidence IDs with --media as described in
README.md. Private storage, source-backed routing, worker jobs and production PostgreSQL
checks require the backend teammate's services and are separate from this one-request check.

To clear credentials from this terminal afterward:

```powershell
Remove-Item Env:GEMINI_API_KEY -ErrorAction SilentlyContinue
Remove-Item Env:GEMINI_MODEL -ErrorAction SilentlyContinue
```

Official references:
- [Billing and free-tier projects](https://ai.google.dev/gemini-api/docs/billing)
- [Model pricing and data use](https://ai.google.dev/gemini-api/docs/pricing)
