import React from "react";
import { AbsoluteFill, Img, staticFile } from "remotion";

interface ThumbnailProps {
  readonly durationInFrames: number;
}

export const Thumbnail: React.FC<ThumbnailProps> = () => {
  return (
    <AbsoluteFill className="bg-white flex items-center justify-center flex-col">
      {/* <div className="flex flex-col items-center justify-center">
        <svg
          version="1.1"
          xmlns="http://www.w3.org/2000/svg"
          xmlnsXlink="http://www.w3.org/1999/xlink"
          width="800"
          height="800"
          viewBox="0, 0, 296.339, 296.339"
          className="max-w-[80%] max-h-[80%] -mb-32 -mt-32"
        >
          <g id="Layer_1" transform="translate(-107.02, -433.4)">
            <g>
              <path
                d="M166.18,496.285 L177.149,496.285 L177.149,505.601 L169.344,520.753 L162.313,520.789 L166.18,505.601 z"
                fill="#000000"
              />
              <path
                d="M235.02,515.656 L235.02,521.632 L191.989,521.632 L191.989,515.656 z"
                fill="#000000"
              />
              <path
                d="M290.223,496.285 L301.192,496.285 L301.192,505.601 L293.387,520.753 L286.356,520.789 L290.223,505.601 z"
                fill="#000000"
              />
              <path
                d="M359.063,515.656 L359.063,521.632 L316.031,521.632 L316.031,515.656 z"
                fill="#000000"
              />
              <path
                d="M160.942,532.088 L188.574,591.256 L181.895,591.256 L154.227,532.088 z"
                fill="#000000"
              />
              <path
                d="M223.242,532.088 L229.922,532.088 L202.289,591.256 L195.574,591.256 z"
                fill="#000000"
              />
              <path
                d="M277.778,566.998 L314.938,566.998 L314.938,572.939 L277.778,572.939 z M277.778,550.439 L314.938,550.439 L314.938,556.381 L277.778,556.381 z"
                fill="#000000"
              />
              <path
                d="M319.125,566.998 L356.285,566.998 L356.285,572.939 L319.125,572.939 z M319.125,550.439 L356.285,550.439 L356.285,556.381 L319.125,556.381 z"
                fill="#000000"
              />
              <path
                d="M181.895,607.688 L188.574,607.688 L160.942,666.856 L154.227,666.856 z"
                fill="#000000"
              />
              <path
                d="M202.289,607.688 L229.922,666.856 L223.242,666.856 L195.574,607.688 z"
                fill="#000000"
              />
              <path
                d="M294.477,601.957 L309.383,601.957 L309.383,606.985 L300.946,606.985 L300.946,661.125 L309.383,661.125 L309.383,666.153 L294.477,666.153 z"
                fill="#000000"
              />
              <path
                d="M341.344,601.957 L341.344,666.153 L326.438,666.153 L326.438,661.125 L334.875,661.125 L334.875,606.985 L326.438,606.985 L326.438,601.957 z"
                fill="#000000"
              />
            </g>
          </g>
        </svg>
        <div className="flex items-center justify-center">
          <Img
            src={staticFile("images/10784-陰.svg")}
            className="h-100 w-auto object-contain"
          />
          <Img
            src={staticFile("images/3307-符.svg")}
            className="h-100 w-auto object-contain"
          />
        </div>
      </div> */}
      <Img
        src={staticFile("images/thumbnail.svg")}
        className="w-full h-full object-contain"
      />
    </AbsoluteFill>
  );
};
