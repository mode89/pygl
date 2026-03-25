<debugging>
Use curl to perform interactive debugging through devdoor.

```bash
# Start app
python hello.py &

# Check devdoor is running
curl http://localhost:8000/status

# Take a screenshot of the current window
curl http://localhost:8000 -d "$(cat <<'EOF'
print("Taking screenshot ...")
_save_screenshot(window, "/tmp/screenshot.png")
print("Done.")
EOF
)"

# Close app
curl http://localhost:8000 -d "_quit(window)"
```
</debugging>
