import { MarkdownMessage } from "../markdown";

type ImageItem = { url: string; label: string; analysis: string };

type ImageGridProps = {
  images: ImageItem[];
};

function ImageCell({ img, full }: { img: ImageItem; full?: boolean }) {
  return (
    <div className={`image-grid__cell${full ? " image-grid__cell--full" : ""}`}>
      {img.label && <div className="image-grid__label">{img.label}</div>}
      <img src={img.url} alt={img.label} className="image-grid__img" />
      {img.analysis && (
        <div className="image-grid__analysis">
          <MarkdownMessage text={img.analysis} />
        </div>
      )}
    </div>
  );
}

export function ImageGrid({ images }: ImageGridProps) {
  if (!images.length) return null;

  const [first, ...rest] = images;

  // Group remaining images into pairs (property map + p-chart per PIN)
  const pairs: ImageItem[][] = [];
  for (let i = 0; i < rest.length; i += 2) {
    pairs.push(rest.slice(i, i + 2));
  }

  return (
    <div className="image-grid">
      {/* Binary map — full width */}
      <ImageCell img={first} full />

      {/* PIN pairs — each pair on its own 2-column row */}
      {pairs.map((pair, pi) => (
        <div key={pi} className="image-grid__pair">
          {pair.map((img, i) => (
            <ImageCell key={i} img={img} />
          ))}
        </div>
      ))}
    </div>
  );
}
