const ACCUTE_ACCENT = "\u{301}"; // Unicode: COMBINING ACUTE ACCENT (U+0301) "́"
const GRAVE_ACCENT = "\u{300}"; // Unicode: COMBINING GRAVE ACCENT (U+0300) "◌̀"
// const CIRCUMFLEX_ACCENT = "̂";
const CARON = "\u{30C}"; // Unicode: COMBINING CARON (U+030C) "̌" (háček)
const DOT_BELOW = "\u{323}"; // Unicode: COMBINING DOT BELOW (U+0323) "̣"

const ACCENTS = [ACCUTE_ACCENT, GRAVE_ACCENT].join("");

function separateTone(rhyme: string): [string, string] {
  const ORIGINAL_TONES = [ACCUTE_ACCENT, GRAVE_ACCENT, CARON];
  for (const tone of ORIGINAL_TONES) {
    if (rhyme.includes(tone)) {
      return [rhyme.replace(tone, ""), tone];
    }
  }
  return [rhyme, ""];
}

function convertWord(word: string): string {
  let result = word.normalize("NFD");

  // Split into CGVC-T

  let onset = "";
  let rhyme = "";

  for (let i = 0; i < result.length; i++) {
    if (result[i].match(/[aeiouɑɨəʉyʷ]/)) {
      onset = result.slice(0, i);
      rhyme = result.slice(i);
      break;
    }
  }

  const ONSET_TABLE = {
    // Bilabial
    p: "p",
    pʰ: "ph",
    b: "b",
    m: "m",

    // Alveolar
    t: "t",
    tʰ: "th",
    d: "d",
    n: "n",
    s: "s",
    z: "z",
    ʦ: "ts",
    ʣ: "dz",
    ʦʰ: "tsh",

    // Alveolo-palatal
    ɕ: "sj",
    ʑ: "zj",
    ʨ: "tj",
    ʨʰ: "tjh",
    ʥ: "dj",
    ɲ: "nj",

    // Retroflex
    ʂ: "sr",
    ʈ: "tr",
    ɖ: "dr",
    ɳ: "nr",
    ꭧ: "tsr",
    ꭧʰ: "tshr",
    ꭦ: "dzr",
    l: "l",

    // Palatal
    j: "j",

    // Velar
    k: "k",
    kʰ: "kh",
    g: "g",
    ŋ: "ng",

    h: "h",
    ʔ: "q",
    ɦ: "gh",
  };

  if (!Object.keys(ONSET_TABLE).includes(onset)) {
    console.warn(`Unknown onset: ${onset}`);
  }

  onset = ONSET_TABLE[onset as keyof typeof ONSET_TABLE] || onset;

  // Remove vowel lengthening
  rhyme = rhyme.replace(/ː/, "");

  let medialNucleus = "";
  let coda = "";
  for (let i = rhyme.length - 1; i >= 0; i--) {
    if (rhyme[i].match(/[^mnŋptkjw]/)) {
      coda = rhyme.slice(i + 1);
      medialNucleus = rhyme.slice(0, i + 1);
      break;
    }
  }

  let [tonelessMedialNucleus, tone] = separateTone(medialNucleus);

  const TONE_TABLE = new Map<string, string>([
    [ACCUTE_ACCENT, "q"],
    [GRAVE_ACCENT, ""],
    [CARON, "h"],
  ]);
  if (tone.length > 0 && !TONE_TABLE.has(tone)) {
    console.warn(`Unknown tone: ${tone}`);
  }
  tone = TONE_TABLE.get(tone) ?? tone;

  // // Remove 平聲 marks (grave accent)
  // rhyme = rhyme.replace(GRAVE_ACCENT, "");

  // // Use grave instead of caron
  // rhyme = rhyme.replace(CARON, GRAVE_ACCENT);

  let medial = "";
  let nucleus = "";

  tonelessMedialNucleus = tonelessMedialNucleus.normalize("NFC");

  if (tonelessMedialNucleus.length == 1) {
    nucleus = tonelessMedialNucleus;
  } else if (tonelessMedialNucleus.length == 2) {
    // if (tonelessMedialNucleus[1].match(/[jw]/)) {
    //   medial = "";
    //   nucleus = tonelessMedialNucleus;
    // } else {
    medial = tonelessMedialNucleus[0];
    nucleus = tonelessMedialNucleus[1];
    // }
  } else {
    // if (tonelessMedialNucleus[0].match(/[jw]/)) {
    //   // wi.e -> wi
    //   // medial = ton
    // }
    medial = tonelessMedialNucleus.slice(0, tonelessMedialNucleus.length - 1);
    nucleus = tonelessMedialNucleus.slice(tonelessMedialNucleus.length - 1);
  }

  const SPECIAL_PAIRS = new Map([
    ["ɨə", "yo"],
    ["ʉu", "u"],
  ]);

  if (SPECIAL_PAIRS.has(`${medial}${nucleus}`)) {
    const converted = SPECIAL_PAIRS.get(`${medial}${nucleus}`);
    if (converted) {
      medial = "";
      nucleus = converted;
    }
  } else {
    const MEDIAL_TABLE = {
      y: "wi",
      ʷ: "w",
      ɨ: "y",
      ị: "y",
      ʉ: "u",
      ỵ: "u",
      i: "i",
    };
    if (medial.length > 0 && !Object.keys(MEDIAL_TABLE).includes(medial)) {
      console.warn(`Unknown medial: ${medial}`);
    }
    medial = MEDIAL_TABLE[medial as keyof typeof MEDIAL_TABLE] || medial;

    const NUCLEUS_TABLE = {
      a: "ae",
      ạ: "ae",
      e: "e",
      ẹ: "ee",
      ɑ: "a",
      ə: "eo",
      i: "i",
      ɨ: "y",
      ị: "yi",
      u: "ou",
      ʉ: "u",
      o: "o",
      ọ: "oeu",
    };
    if (nucleus.length > 0 && !Object.keys(NUCLEUS_TABLE).includes(nucleus)) {
      console.warn(`Unknown nucleus: ${nucleus}`);
    }
    nucleus = NUCLEUS_TABLE[nucleus as keyof typeof NUCLEUS_TABLE] || nucleus;
  }

  // for (let i = 0; i < tonelessMedialNucleus.length; i++) {
  //   if (tonelessMedialNucleus[i].match(/[aeiouɑɨəʉyʷ]/)) {
  //     medial = tonelessMedialNucleus.slice(0, i);
  //     nucleus = tonelessMedialNucleus.slice(i);
  //     break;
  //   }
  // }

  const CODA_TABLE = {
    m: "m",
    n: "n",
    ŋ: "ng",
    p: "p",
    t: "t",
    k: "k",
    w: "w",
    j: "j",
  };
  if (coda.length > 0 && !Object.keys(CODA_TABLE).includes(coda)) {
    console.warn(`Unknown coda: ${coda}`);
  }
  coda = CODA_TABLE[coda as keyof typeof CODA_TABLE] || coda;

  // result = result.replace(/^ɦʉu/, "u");
  // result = result.replace(/^ɦʉ/, "u");
  // result = result.replace(/^ɦ/, "gh");

  // result = result.replace(/^ʂ/, "sr");
  // result = result.replace(/^ʈ/, "tr");

  // result = result.replace(/^ɲ/, "nj");

  // result = result.replace(/ŋ/, "ng");

  // result = result.replace(/uk$/, "ouk");
  // result = result.replace(
  //   new RegExp(`${"ị".normalize("NFD")}([${ACCENTS}]?)`, "g"),
  //   "y$1i",
  // );

  // // result = result.replace(/^j/, "y");
  // // kɨ̀j -> kyih
  // result = result.replace(new RegExp(`ʉu([${ACCENTS}]?)`), "u$1");
  // result = result.replace(new RegExp(`ɨ([${ACCENTS}]?)j`), "y$1j");
  // result = result.replace(new RegExp(`ə([${ACCENTS}]?)j`), "e$1oj");

  // result = result.replace(
  //   new RegExp(`(?![i])a([${POINT_BOTTOM}]?)([${ACCENTS}]?)`, "g"),
  //   "a$2e",
  // );
  // // result = result.replace(new RegExp(`a([${ACCENTS}])?`, "g"), "a$1e");
  // result = result.replace(
  //   new RegExp(`i(?:[${POINT_BOTTOM}]?)a([${ACCENTS}]?)`),
  //   "ya$1",
  // );
  // result = result.replace(/ɑ/, "a");
  // result = result.replace(/ɨə/, "yo");
  // result = result.replace(/ɨ/, "y");
  // result = result.replace(/ʉ/, "u");

  // result = result.replace(/yy/, "y");
  // // Recompose

  if (
    (onset === "gh" && nucleus === "u") ||
    (onset === "gh" && nucleus === "y") ||
    (onset === "gh" && medial === "u") ||
    (onset === "gh" && medial === "y")
  ) {
    onset = "";
  }

  result = [onset, medial, nucleus, coda, tone].join("").normalize("NFC");

  return result;
}

export function convertIPAToTranscription(ipa: string): string {
  //  pèn ɖiàŋ ʨiáː ɦɑ̀ː . ʂɨə́ː jɨ́ː jyak kɨ̀j kʰị̌ː jiáː . kɨ̀j kʰị̌ː ʨiáː ɦɑ̀ː . ʂɨə́ː jɨ́ː də̌j ɲìn lɨk jiáː . ɲièn kɨ̀j kʰị̌ː ʨɨ̀ː lɨk jiáː kʷɑ́ŋ . gɨ̀ː sʷɑ̌n jiáː suk . jʷìː ʈiěː pʉùː də̌j jiáː . kǒː ɦʉúː ʈiěː ʨiáː ʥǐn mʉùː ɦʉón lɨə̌ː . ɦạ́ː pịt ʦʰèn ŋɨə̀n . ɲɨə̀ː kʉ̀n liǎŋ ɲièn . ɲɨə̀ː jɨɑk pʉɑ̀ŋ ɲièn . ɦʉ̌j ʨɨ̀ː ɖiàŋ ɕɨk . kɨ̀j kʰị̌ː kɨ̌j mịàŋ ʨɨ̀ː . nə́j nə̀ŋ ɦỵèː ɲìn ʂɨə́ː ʂɨ́ː . ɦʷək jién sèŋ mʉ̀n . ɦʷək sek ꭦɨ̌ː lɨ́ː .

  //  pen driaeng tjiaeq gha . sryoq jyq jwiaek kyj khyih jiaeq . kyj khyih tjiaeq gha . sryoq jyq deojh njin lyk jiaeq njien kyj hkyih tjy lyk jiaeq kwangq . gy swanq jiaeq souk . jiw trieh pu dejh jaeq.

  // Decompose
  return ipa.split(" ").map(convertWord).join(" ");
}
