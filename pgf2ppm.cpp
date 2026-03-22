// pgf2ppm: reads a PGF file from stdin, writes PPM (RGB) or PAM (RGBA) to stdout
#include <PGFimage.h>
#include <PGFstream.h>
#include <cstdio>
#include <cstdlib>
#include <vector>

int main() {
    // Read all of stdin into a buffer
    std::vector<unsigned char> input;
    {
        unsigned char buf[65536];
        size_t n;
        while ((n = fread(buf, 1, sizeof(buf), stdin)) > 0)
            input.insert(input.end(), buf, buf + n);
    }
    if (input.empty()) {
        fprintf(stderr, "pgf2ppm: empty input\n");
        return 1;
    }

    try {
        CPGFMemoryStream stream(input.data(), input.size());
        CPGFImage pgf;
        pgf.Open(&stream);
        pgf.Read();

        int w = pgf.Width();
        int h = pgf.Height();
        int channels = pgf.Channels();
        int bpp = pgf.BPP();
        BYTE mode = pgf.Mode();

        // Always output PPM (P6) as RGB, dropping alpha if present
        int outBpp = 24;
        int outChannels = 3;
        int pitch = w * outChannels;
        // Align pitch to 4 bytes
        pitch = (pitch + 3) & ~3;
        std::vector<UINT8> bitmap(pitch * h);

        // Channel map: default nullptr works for RGB/RGBA
        pgf.GetBitmap(pitch, bitmap.data(), outBpp);

        // Output PPM format (P6, RGB)
        fprintf(stdout, "P6\n%d %d\n255\n", w, h);
        // GetBitmap returns BGR bottom-up, convert to RGB top-down
        for (int y = h - 1; y >= 0; y--) {
            UINT8 *row = bitmap.data() + y * pitch;
            for (int x = 0; x < w; x++) {
                UINT8 b = row[x*3 + 0];
                UINT8 g = row[x*3 + 1];
                UINT8 r = row[x*3 + 2];
                fputc(r, stdout);
                fputc(g, stdout);
                fputc(b, stdout);
            }
        }
    } catch (IOException& e) {
        fprintf(stderr, "pgf2ppm: PGF decode error %d\n", e);
        return 1;
    }
    return 0;
}
