#!/usr/bin/env python3
"""Regenerate blog/posts.json — the list of blog post ids the site loads.

Static hosting (GitHub Pages) can't list a directory at runtime, so this stands
in for that: run it whenever you add or remove a post in blog/, and the site
picks up the change. Run from the project root:

    python3 scan_blog.py

The site re-sorts by each post's @DATE anyway; the reverse sort here just keeps
the manifest tidy (newest first) for date-prefixed filenames.
"""
import glob
import json
import os

ids = [os.path.splitext(os.path.basename(p))[0] for p in glob.glob('blog/*.txt')]
ids.sort(reverse=True)

with open('blog/posts.json', 'w') as f:
    json.dump(ids, f, indent=0)

print('wrote blog/posts.json (%d posts): %s' % (len(ids), ', '.join(ids)))
