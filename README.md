Fetch Notion help docs.
Chunking with 750 characters soft limit, one or more headlines each chunk.
Save chunks to a file.

## How-to
```bash
pip install -r requirements.txt

python main.py
```

Results will be in file `results.txt`

To read the file:
```python
with open("results.txt", "r") as file:
  chunks = eval(file.read())
```

