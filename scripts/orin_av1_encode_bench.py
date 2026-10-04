import av, numpy as np, time, os
print("codecs:", [c for c in ("libsvtav1", "libx264", "h264", "libaom-av1") if c in av.codecs_available])
for codec, w, h, n in (("libsvtav1", 640, 480, 450), ("libsvtav1", 320, 200, 450)):
    path = "/tmp/enc_%d.mp4" % w
    out = av.open(path, "w"); st = out.add_stream(codec, rate=30); st.width, st.height = w, h; st.pix_fmt = "yuv420p"
    rng = np.random.default_rng(0)
    frames = [(rng.integers(0, 64, (h, w, 3), dtype=np.uint8) + 96).astype(np.uint8) for _ in range(8)]
    t = time.time()
    for i in range(n):
        for p in st.encode(av.VideoFrame.from_ndarray(frames[i % 8], format="rgb24")): out.mux(p)
    for p in st.encode(): out.mux(p)
    out.close(); dt = time.time() - t
    print("%s %dx%d: %d frames in %.1fs (%.0f fps), file %.1f MB" % (codec, w, h, n, dt, n / dt, os.path.getsize(path) / 1e6))
