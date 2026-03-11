#!/usr/bin/env python3
"""Generate bcrypt hash for passwords."""

import bcrypt
import sys

if len(sys.argv) != 2:
    print("Usage: python generate_hash.py <password>")
    sys.exit(1)

password = sys.argv[1]
hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
print(hashed.decode('utf-8'))