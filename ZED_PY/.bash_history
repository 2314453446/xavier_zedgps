python3 -c "import pyzed.sl as sl; print(sl)"
sudo python3 -c "import pyzed.sl as sl; print(sl)"
python3 -c "import pyzed.sl as sl; print(sl)"
chmod 777 get_python_api.py 
python3 get_python_api.py 
which python3
python3 - <<'PY'
import sys, site
print("exe:", sys.executable)
print("user_site:", site.getusersitepackages())
print("sys.path:")
for p in sys.path:
    print(" ", p)
PY

sudo python3 - <<'PY'
import sys, site
print("exe:", sys.executable)
print("user_site:", site.getusersitepackages())
print("sys.path:")
for p in sys.path:
    print(" ", p)
PY

python3 - <<'PY'
try:
    import pyzed
    print("pyzed module:", pyzed)
    print("pyzed file:", getattr(pyzed, "__file__", None))
    print("pyzed path:", getattr(pyzed, "__path__", None))
except Exception as e:
    print("import pyzed failed:", repr(e))
PY

find ~ -maxdepth 4 \( -type d -name 'pyzed' -o -type f -name 'pyzed.py' \) 2>/dev/null
ls -ld /usr/local/lib/python3.8/dist-packages/pyzed
chmod 777 get_python_api.py 
python3 get_python_api.py 
cd /usr/local/
ll
cd lib/
ll
cd python3.8/
ll
cd dist-packages/
ll
sudo -i
exit
cd third_party/zed-sdk/global\ localization/recording/python/
python recording.py 
python3 recording.py 
kill -9 %1
exit
cd third_party/zed-sdk/global localization/recording/python
cd third_party/zed-sdk/global localization/recording
cd third_party/zed-sdk/global\ localization/recording/python/
python3 recording.py 
kill 1%
kill -9 %1
cd /usr/local/zed/resources/
ll
cd ~/third_party/zed-sdk/global\ localization/recording/python/
python recording.py 
python3 recording.py 
kill -9 %1
exit
