# Demo example

Create a text call with:

- Title: `Healthy street tree descriptions`
- Description: `Collect short observations of healthy trees beside public roads.`
- Criteria: `A clear description of one healthy street tree, its visible condition, and its urban setting.`
- Review mode: `AI-assisted`
- Standard reward: `1 DBT`
- High reward: `2 DBT`
- Maximum accepted: `3`

After funding the call, sign in with another wallet and upload `sample-tree.txt`. The AI result is only a recommendation; inspect the file and choose the final tier as the caller.

## AI evaluator check

For a quick text-model demonstration, create an AI-assisted text call with criteria
`a clear readable street sign`, then submit these files from different contributor wallets:

- `ai-test-text-matching.txt` should be recommended `accept/high`.
- `ai-test-text-unrelated.txt` should be recommended `reject/standard`.

For the open Street Sign Photos image call, extract a few individual JPEG/PNG frames from one
of these research datasets; the MVP accepts one image per contribution, not an archive:

- [LISA Traffic Signs Dataset](https://cvrr.ucsd.edu/lisa-traffic-signs-dataset) has annotated
  US traffic signs in full camera frames and is the closest match to the current call.
- [German Traffic Sign Benchmarks](https://github.com/houbensebastian/GermanTrafficSignBenchmarks)
  provides GTSRB cropped sign images and GTSDB full-scene detection images.

Use five obvious matching sign images, two blurry or dark images, and three unrelated photos.
This small balanced set makes `accept`, `unsure`, and `reject` behavior easy to demonstrate.

