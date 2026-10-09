"use client";

import type { LookProps, Looks } from "./registry";
import { Caption, DataButton, Picture } from "./shared";
import { MindMap, WordCloud } from "../Charts";
import "./visual.css";


/* ---------- image ---------- */

function ImgBanner({ b, p, limits, imageBase, num }: LookProps<"image">) {
  return (
    <figure className="img v-vi v-im-banner">
      <Picture src={b.src} alt={b.alt} p={p} imageBase={imageBase} />
      <Caption p={p} b={b} num={num} kind="figure" limits={limits} />
    </figure>
  );
}

/** The picture on the right, its caption hangs under the empty left column and points at it. */
function ImgOffset({ b, p, limits, imageBase, num }: LookProps<"image">) {
  return (
    <figure className="img v-vi v-im-offset">
      <div className="v-im-offset-in">
        <Picture src={b.src} alt={b.alt} p={p} imageBase={imageBase} />
        <Caption p={p} b={b} num={num} kind="figure" limits={limits} />
      </div>
    </figure>
  );
}

/** A 4:3 picture on the left, the caption stands beside it under a rule. */
function ImgSide({ b, p, limits, imageBase, num }: LookProps<"image">) {
  return (
    <figure className="img v-vi v-im-side">
      <div className="v-im-side-in">
        <Picture src={b.src} alt={b.alt} p={p} imageBase={imageBase} />
        <Caption p={p} b={b} num={num} kind="figure" limits={limits} />
      </div>
    </figure>
  );
}

/* ---------- mindmap and word cloud: the original drawings, no alternative ---------- */

function MindMapClassic({ b, p, limits, num }: LookProps<"mindmap">) {
  return (
    <figure>
      <div className="panel has-over">
        <DataButton p={p} />
        <MindMap b={b} />
        <ul className="mm-list">
          {b.branches.map((br, i) => (
            <li key={i}><b>{br.title}</b><span>{br.leaves.join(", ")}</span></li>
          ))}
        </ul>
      </div>
      <Caption p={p} b={b} num={num} kind="figure" limits={limits} />
    </figure>
  );
}

function WordCloudClassic({ b, p, limits, num }: LookProps<"wordcloud">) {
  return (
    <figure>
      <div className="panel has-over"><DataButton p={p} /><WordCloud b={b} /></div>
      <Caption p={p} b={b} num={num} kind="figure" limits={limits} />
    </figure>
  );
}

export const LOOKS_VISUAL: Looks = {
  image: [
    { name: "Breites Banner", View: ImgBanner },
    { name: "Versetzte Unterschrift", fits: (b) => !!b.caption, View: ImgOffset },
    { name: "Unterschrift seitlich", fits: (b) => !!b.caption, View: ImgSide },
  ],
  mindmap: [{ name: "Gedankenkarte", View: MindMapClassic }],
  wordcloud: [{ name: "Wortwolke", View: WordCloudClassic }],
};
