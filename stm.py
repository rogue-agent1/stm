#!/usr/bin/env python3
"""stm - Software transactional memory with optimistic concurrency."""
import sys, json, threading, time, random

class TVar:
    _next_id = 0
    def __init__(self, value):
        self.id = TVar._next_id; TVar._next_id += 1
        self._value = value
        self._version = 0
        self._lock = threading.Lock()
    
    def _read(self):
        return self._value, self._version
    
    def _write(self, value, expected_version):
        with self._lock:
            if self._version != expected_version:
                return False
            self._value = value
            self._version += 1
            return True

class Transaction:
    def __init__(self):
        self.reads = {}
        self.writes = {}
        self.committed = False
    
    def read(self, tvar):
        if tvar.id in self.writes:
            return self.writes[tvar.id]
        val, ver = tvar._read()
        self.reads[tvar.id] = (tvar, ver)
        return val
    
    def write(self, tvar, value):
        if tvar.id not in self.reads:
            _, ver = tvar._read()
            self.reads[tvar.id] = (tvar, ver)
        self.writes[tvar.id] = value

class STM:
    _stats_lock = threading.Lock()
    stats = {"commits": 0, "retries": 0}
    
    @staticmethod
    def atomically(fn, max_retries=100):
        for attempt in range(max_retries):
            tx = Transaction()
            try:
                result = fn(tx)
            except Exception:
                with STM._stats_lock: STM.stats["retries"] += 1
                continue
            # Validate reads
            valid = True
            for tvar_id, (tvar, ver) in tx.reads.items():
                _, current_ver = tvar._read()
                if current_ver != ver:
                    valid = False; break
            if not valid:
                with STM._stats_lock: STM.stats["retries"] += 1
                continue
            # Commit writes
            all_ok = True
            for tvar_id, value in tx.writes.items():
                tvar, ver = tx.reads[tvar_id]
                if not tvar._write(value, ver):
                    all_ok = False; break
            if all_ok:
                with STM._stats_lock: STM.stats["commits"] += 1
                return result
            with STM._stats_lock: STM.stats["retries"] += 1
        raise RuntimeError("STM: too many retries")

def main():
    print("Software Transactional Memory demo\n")
    account_a = TVar(1000)
    account_b = TVar(1000)
    
    def transfer(tx, amount=100):
        a = tx.read(account_a)
        b = tx.read(account_b)
        tx.write(account_a, a - amount)
        tx.write(account_b, b + amount)
        return (a - amount, b + amount)
    
    # Concurrent transfers
    threads = []
    for _ in range(10):
        t = threading.Thread(target=lambda: STM.atomically(lambda tx: transfer(tx, 50)))
        threads.append(t)
    for t in threads: t.start()
    for t in threads: t.join()
    
    final_a, _ = account_a._read()
    final_b, _ = account_b._read()
    print(f"Account A: {final_a}")
    print(f"Account B: {final_b}")
    print(f"Total: {final_a + final_b} (should be 2000)")
    print(f"Stats: {json.dumps(STM.stats, indent=2)}")

if __name__ == "__main__":
    main()
