"""Issues a sample notice through the running API, then derives the five hackathon demo files into ./samples.
Usage: python scripts/make_demos.py --api http://localhost:8000 --email admin@college.edu --password '...'
Requires: pip install requests opencv-python-headless numpy"""
import argparse, io, datetime as dt, numpy as np, cv2, requests

def page(lines, w=1024, h=1400):
    im = np.full((h, w, 3), 255, np.uint8)
    for i, t in enumerate(lines): cv2.putText(im, t, (40, 90 + i * 70), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (20, 20, 20), 2)
    return im
def png(a): return cv2.imencode(".png", a)[1].tobytes()
def jpg(a, q): return cv2.imencode(".jpg", a, [cv2.IMWRITE_JPEG_QUALITY, q])[1].tobytes()
def dec(b): return cv2.imdecode(np.frombuffer(b, np.uint8), 1)

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--api", default="http://localhost:8000"); ap.add_argument("--email", required=True); ap.add_argument("--password", required=True)
    a = ap.parse_args(); H = {"Authorization": "Bearer " + requests.post(f"{a.api}/api/auth/login", json={"email": a.email, "password": a.password}).json()["access_token"]}
    base = page(["EXAMINATION NOTICE", "", "Semester exams begin on 12 December 2026.", "Hall tickets are issued from 1 December.", "", "Controller of Examinations"])
    exp = (dt.date.today() + dt.timedelta(days=60)).isoformat(); r = requests.post(f"{a.api}/api/notices/create", headers=H, files={"file": ("exam.png", png(base))},
        data=dict(title="Semester Examination Schedule", department="Examinations", category="exam", issue_date=dt.date.today().isoformat(), expiry_date=exp))
    r.raise_for_status(); n = r.json(); nid = n["notice_id"]
    auth = requests.get(f"{a.api}{n['download']}", headers=H).content; qr = requests.get(f"{a.api}{n['qr']}").content
    out = lambda name, b: open(f"samples/{name}", "wb").write(b)
    out("1_genuine.png", auth); img = dec(auth)
    t = img.copy(); cv2.rectangle(t, (40, 150), (1000, 200), (255, 255, 255), -1)       # demo 2: change the exam date
    cv2.putText(t, "Semester exams begin on 20 December 2026.", (40, 230 - 20), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (20, 20, 20), 2); out("2_modified_date.png", png(t))
    out("3_whatsapp_compressed.jpg", jpg(cv2.resize(img, None, fx=0.75, fy=0.75, interpolation=cv2.INTER_AREA), 55))   # demo 3
    fake = page(["HOLIDAY NOTICE", "", "College remains closed on 15 December 2026."]); q = cv2.resize(dec(qr), (160, 160), interpolation=cv2.INTER_NEAREST)
    fake[-200:-40, -200:-40] = q; out("4_fake_with_copied_qr.png", png(fake))                                   # demo 4
    h, w = img.shape[:2]; out("5_screenshot_cropped.jpg", jpg(img[int(h * .03):int(h * .97), int(w * .03):int(w * .97)], 60))   # demo 5
    print("Issued", nid, "- demo files written to ./samples")
if __name__ == "__main__": main()
