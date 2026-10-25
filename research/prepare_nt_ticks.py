"""Prepare Last-only historical tick text. Does not import or modify NinjaTrader DB."""
import argparse, hashlib, json
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import pyarrow.parquet as pq

def prepare(source, destination):
    source, destination = Path(source), Path(destination)
    if destination.exists():
        raise FileExistsError(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    rows = volume = 0
    previous = None
    first = last = None
    temp = destination.with_suffix('.pending')
    try:
        with temp.open('w', encoding='ascii', newline='') as output:
            for batch in pq.ParquetFile(source).iter_batches(batch_size=250000):
                ts = batch.column('Timestamp').cast('int64').to_numpy()
                kinds = batch.column('MarketDataType').to_numpy()
                prices = batch.column('Price').to_numpy()
                volumes = batch.column('Volume').to_numpy()
                mask = kinds == 2  # NRD Last, not quote updates or daily volume.
                for stamp, price, size in zip(ts[mask], prices[mask], volumes[mask]):
                    stamp, size = int(stamp), int(size)
                    if (previous is not None and stamp < previous) or stamp % 100:
                        raise ValueError('Unordered timestamp or finer than 100ns')
                    if not np.isfinite(price) or price <= 0 or size <= 0 or abs(price*4-round(price*4)) > 1e-8:
                        raise ValueError('Invalid NQ price/size')
                    seconds, nano = divmod(stamp, 1000000000)
                    time = datetime.fromtimestamp(seconds, timezone.utc).strftime('%Y%m%d %H%M%S')
                    output.write(f'{time} {nano//100:07d};{price:.2f};{size}\n')
                    previous = last = stamp
                    if first is None: first = stamp
                    rows += 1
                    volume += size
        if not rows: raise ValueError('No trades')
        temp.replace(destination)
    except Exception:
        if temp.exists(): temp.unlink()
        raise
    report = dict(source=str(source), output=str(destination), rows=rows, volume=volume,
                  first_ns=first, last_ns=last, timezone='UTC', format='Last ticks, 100ns',
                  source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                  output_sha256=hashlib.sha256(destination.read_bytes()).hexdigest(),
                  imported=False, bid_ask_included=False, L2_included=False)
    destination.with_suffix('.manifest.json').write_text(json.dumps(report, indent=2))
    return report

if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('source'); parser.add_argument('destination')
    args=parser.parse_args()
    print(json.dumps(prepare(args.source,args.destination),indent=2))

