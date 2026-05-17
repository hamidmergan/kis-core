import { ImageResponse } from "next/og";

export const size = { width: 32, height: 32 };
export const contentType = "image/png";

export default function Icon() {
  return new ImageResponse(
    (
      <div
        style={{
          width: 32,
          height: 32,
          background: "rgb(0, 66, 97)",
          borderRadius: 6,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          color: "white",
          fontSize: 15,
          fontWeight: 800,
          letterSpacing: "-0.5px",
          fontFamily: "sans-serif",
        }}
      >
        KIS
      </div>
    ),
    { ...size }
  );
}
