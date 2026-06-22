import sys, os

def main(path, n_records):
    out = os.path.splitext(os.path.basename(path))[0] + "_sliced.json"
    print(f"Slicing the first {n_records} records from: {path}...")
    
    count = 0
    try:
        with open(path, 'r', encoding='utf-8') as infile, open(out, 'w', encoding='utf-8') as outfile:
            for line in infile:
                outfile.write(line)
                count += 1
                if count >= n_records:
                    break
    except FileNotFoundError:
        print("File not found", file=sys.stderr); sys.exit(2)

    print(f"Successfully saved {count} records to {out}")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python3 ais_slice.py <input.json> <number_of_records>", file=sys.stderr); sys.exit(1)
    
    try:
        n = int(sys.argv[2])
    except ValueError:
        print("Error: The number of records must be an integer.", file=sys.stderr); sys.exit(1)
        
    main(sys.argv[1], n)