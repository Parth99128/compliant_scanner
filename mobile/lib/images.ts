import * as FileSystem from "expo-file-system";
import { manipulateAsync, SaveFormat } from "expo-image-manipulator";
import { MAX_UPLOAD_BYTES, mimeForUri } from "./api";

export interface PreparedImage {
  uri: string;
  sizeBytes: number | null;
  compressed: boolean;
  mime: string;
}

const MAX_SIDE_PX = 1600;

/** Downscale + recompress one photo so the 10 MB backend cap is never hit. Never throws. */
export async function prepareImage(uri: string): Promise<PreparedImage> {
  const mime = mimeForUri(uri);
  try {
    const sized = await sizeOf(uri);
    if (sized != null && sized <= MAX_UPLOAD_BYTES) {
      // Pixel-cap huge photos anyway: 4000px+ wastes upload time, no OCR gain.
      // If the file is already small we still try a cheap bounded resize; on any
      // failure the original URI is returned untouched.
      try {
        const out = await manipulateAsync(uri, [{ resize: { width: MAX_SIDE_PX } }], {
          compress: 0.85,
          format: SaveFormat.JPEG,
        });
        if (out?.uri) {
          return { uri: out.uri, sizeBytes: await sizeOf(out.uri), compressed: true, mime: "image/jpeg" };
        }
      } catch {
        /* keep original */
      }
      return { uri, sizeBytes: sized, compressed: false, mime };
    }
    const out = await manipulateAsync(uri, [{ resize: { width: MAX_SIDE_PX } }], {
      compress: 0.8,
      format: SaveFormat.JPEG,
    });
    if (!out?.uri) return { uri, sizeBytes: sized, compressed: false, mime };
    return { uri: out.uri, sizeBytes: await sizeOf(out.uri), compressed: true, mime: "image/jpeg" };
  } catch {
    return { uri, sizeBytes: null, compressed: false, mime };
  }
}

async function sizeOf(uri: string): Promise<number | null> {
  try {
    const info = await FileSystem.getInfoAsync(uri);
    if (!info.exists) return null;
    const s = (info as unknown as { size?: unknown }).size;
    return typeof s === "number" ? s : null;
  } catch {
    return null;
  }
}
