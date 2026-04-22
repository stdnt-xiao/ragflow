import { memo, useEffect, useRef } from 'react';
import {
  AreaHighlight,
  Highlight,
  IHighlight,
  PdfHighlighter,
  PdfLoader,
  Popup,
} from 'react-pdf-highlighter';

import { Spin } from '@/components/ui/spin';
// import FileError from '@/pages/document-viewer/file-error';
import { Authorization } from '@/constants/authorization';
import { cn } from '@/lib/utils';
import FileError from '@/pages/document-viewer/file-error';
import { getAuthorization } from '@/utils/authorization-util';
import { useCatchDocumentError } from './hooks';
type PdfLoaderProps = React.ComponentProps<typeof PdfLoader> & {
  httpHeaders?: Record<string, string>;
};

const Loader = PdfLoader as React.ComponentType<PdfLoaderProps>;
export interface IProps {
  highlights?: IHighlight[];
  setWidthAndHeight?: (width: number, height: number) => void;
  url: string;
  className?: string;
}
const HighlightPopup = ({
  comment,
}: {
  comment: { text: string; emoji: string };
}) =>
  comment.text ? (
    <div className="Highlight__popup">
      {comment.emoji} {comment.text}
    </div>
  ) : null;

// TODO: merge with DocumentPreviewer
const PdfPreview = ({
  highlights: state,
  setWidthAndHeight,
  url,
  className,
}: IProps) => {
  // const url = useGetDocumentUrl();

  const ref = useRef<((highlight: IHighlight) => void) | null>(null);
  const pendingHighlightRef = useRef<IHighlight | null>(null);
  const error = useCatchDocumentError(url);

  const resetHash = () => {};

  // Whenever `url` changes we start over: the PdfHighlighter remounts
  // and scrollRef will be re-assigned via onDocumentReady.
  useEffect(() => {
    ref.current = null;
  }, [url]);

  // Try to scroll to the first highlight. If the PDF isn't ready yet
  // (ref.current not assigned), stash it — scrollRef callback below
  // will flush the pending highlight once the document is ready.
  useEffect(() => {
    const target = state && state.length > 0 ? state[0] : null;
    if (!target) {
      pendingHighlightRef.current = null;
      return;
    }
    if (ref.current) {
      ref.current(target);
      pendingHighlightRef.current = null;
    } else {
      pendingHighlightRef.current = target;
    }
  }, [state]);

  const httpHeaders = {
    [Authorization]: getAuthorization(),
  };

  return (
    <div
      className={cn(
        'relative size-full rounded overflow-hidden',
        '[&_.pdfViewer.removePageBorders_.page]:last-of-type:mb-0',
        className,
      )}
    >
      <Loader
        url={url}
        httpHeaders={httpHeaders}
        beforeLoad={
          <div className="absolute inset-0 flex items-center justify-center">
            <Spin />
          </div>
        }
        workerSrc="/pdfjs-dist/pdf.worker.min.js"
        errorMessage={<FileError>{error}</FileError>}
      >
        {(pdfDocument) => {
          pdfDocument.getPage(1).then((page) => {
            const viewport = page.getViewport({ scale: 1 });
            const width = viewport.width;
            const height = viewport.height;
            setWidthAndHeight?.(width, height);
          });

          return (
            <PdfHighlighter
              pdfDocument={pdfDocument}
              enableAreaSelection={(event) => event.altKey}
              onScrollChange={resetHash}
              scrollRef={(scrollTo) => {
                ref.current = scrollTo;
                // Document is now ready. If the user clicked a citation
                // before loading finished, jump to it now.
                const pending = pendingHighlightRef.current;
                if (pending) {
                  pendingHighlightRef.current = null;
                  scrollTo(pending);
                }
              }}
              onSelectionFinished={() => null}
              highlightTransform={(
                highlight,
                index,
                setTip,
                hideTip,
                viewportToScaled,
                screenshot,
                isScrolledTo,
              ) => {
                const isTextHighlight = !(
                  highlight.content && highlight.content.image
                );

                const component = isTextHighlight ? (
                  <Highlight
                    isScrolledTo={isScrolledTo}
                    position={highlight.position}
                    comment={highlight.comment}
                  />
                ) : (
                  <AreaHighlight
                    isScrolledTo={isScrolledTo}
                    highlight={highlight}
                    onChange={() => {}}
                  />
                );

                return (
                  <Popup
                    popupContent={<HighlightPopup {...highlight} />}
                    onMouseOver={(popupContent) =>
                      setTip(highlight, () => popupContent)
                    }
                    onMouseOut={hideTip}
                    key={index}
                  >
                    {component}
                  </Popup>
                );
              }}
              highlights={state || []}
            />
          );
        }}
      </Loader>
    </div>
  );
};

export default memo(PdfPreview);
export { PdfPreview };
