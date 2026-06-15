import sys, json, os, time

def main(path):
    out = os.path.splitext(os.path.basename(path))[0] + "_cleaned.json"
    print(f"Starting cleanup of: {path}...")
    
    total_lines = 0
    valid_lines = 0
    start_time = time.time()

    try:
        with open(path, 'r', encoding='utf-8') as infile, open(out, 'w', encoding='utf-8') as outfile:
            for line in infile:
                total_lines += 1
                
                # fast text-based filter to skip terminal/system noise
                if '{"class":"AIS"' not in line:
                    continue
                
                # robustness filter to ensure valid JSON formatting
                try:
                    json.loads(line)
                    outfile.write(line)
                    valid_lines += 1
                except json.JSONDecodeError:
                    continue
    except FileNotFoundError:
        print("File not found", file=sys.stderr); sys.exit(2)

    duration = time.time() - start_time
    print(f"\nCleanup Report:")
    print(f"  Time elapsed: {duration:.2f} seconds")
    print(f"  Total lines analyzed: {total_lines:,}")
    print(f"  Valid AIS records saved: {valid_lines:,}")
    print(f"Cleaned file saved to {out}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 ais_clean.py <input.json>", file=sys.stderr); sys.exit(1)
    main(sys.argv[1])