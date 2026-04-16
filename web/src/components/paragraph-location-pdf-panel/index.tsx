import { useGetDocumentUrl } from '@/hooks/use-document-request';
import { ParagraphLocationRef } from '@/interfaces/database/chat';
import { cn } from '@/lib/utils';
import { LucidePanelRightClose } from 'lucide-react';
import { useCallback, useMemo, useState } from 'react';
import { IHighlight } from 'react-pdf-highlighter';
import PdfPreview from '../document-preview/pdf-preview';
import { Button } from '../ui/button';

interface ParagraphLocationPdfPanelProps {
  locationRef: ParagraphLocationRef | null;
  onClose: () => void;
  width?: number;
}

export function ParagraphLocationPdfPanel({
  locationRef,
  onClose,
  width = 520,
}: ParagraphLocationPdfPanelProps) {
  const documentId = locationRef?.doc_id ?? '';
  const getDocumentUrl = useGetDocumentUrl(documentId);
  const url = getDocumentUrl(documentId);
  const [pageSize, setPageSize] = useState({ width: 849, height: 1200 });

  const handleSetWidthAndHeight = useCallback((w: number, h: number) => {
    setPageSize((prev) => {
      if (prev.width === w && prev.height === h) return prev;
      return { width: w, height: h };
    });
  }, []);

  const highlights = useMemo<IHighlight[]>(() => {
    if (!locationRef) return [];
    const rect = {
      x1: locationRef.x0,
      y1: locationRef.y0,
      x2: locationRef.x1,
      y2: locationRef.y1,
      width: pageSize.width,
      height: pageSize.height,
      pageNumber: locationRef.page,
    };
    return [
      {
        id: `ploc-${locationRef.doc_id}-${locationRef.page}`,
        comment: { text: `p.${locationRef.page}`, emoji: '' },
        position: {
          boundingRect: rect,
          rects: [rect],
          pageNumber: locationRef.page,
        },
        content: { text: '' },
      },
    ];
  }, [locationRef, pageSize]);

  return (
    <section
      className={cn(
        'transition-[width] ease-out duration-300 flex-shrink-0 flex flex-col overflow-hidden border-l border-border',
        locationRef ? `w-[${width}px]` : 'w-0',
      )}
    >
      {locationRef && (
        <>
          <div className="p-4 pb-2 flex justify-between items-center text-sm font-medium shrink-0">
            <span
              className="truncate max-w-[360px]"
              title={locationRef.doc_name}
            >
              {locationRef.doc_name}
              <span className="text-text-sub-title ml-1 font-normal">
                p.{locationRef.page}
              </span>
            </span>
            <Button
              variant="transparent"
              size="icon-sm"
              className="border-0 shrink-0"
              onClick={onClose}
            >
              <LucidePanelRightClose className="size-4 cursor-pointer" />
            </Button>
          </div>

          <div className="flex-1 min-h-0 overflow-hidden">
            {url && documentId && (
              <PdfPreview
                className="p-0 !h-full w-full"
                highlights={highlights}
                setWidthAndHeight={handleSetWidthAndHeight}
                url={url}
                colorHighlights
              />
            )}
          </div>
        </>
      )}
    </section>
  );
}

export default ParagraphLocationPdfPanel;
