import { useGetDocumentUrl } from '@/hooks/use-document-request';
import { ParagraphLocationRef } from '@/interfaces/database/chat';
import { cn } from '@/lib/utils';
import { LucidePanelRightClose } from 'lucide-react';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { IHighlight } from 'react-pdf-highlighter';
import PdfPreview from '../document-preview/pdf-preview';
import { Button } from '../ui/button';

interface ParagraphLocationPdfPanelProps {
  locationRef: ParagraphLocationRef | null;
  onClose: () => void;
  width?: number;
}

const MIN_WIDTH = 320;
const MAX_WIDTH = 1200;
const STORAGE_KEY = 'ragflow:paragraph-pdf-panel-width';

export function ParagraphLocationPdfPanel({
  locationRef,
  onClose,
  width = 520,
}: ParagraphLocationPdfPanelProps) {
  const documentId = locationRef?.doc_id ?? '';
  const getDocumentUrl = useGetDocumentUrl(documentId);
  const url = getDocumentUrl(documentId);
  const [pageSize, setPageSize] = useState({ width: 849, height: 1200 });

  // Resizable width state (persisted in localStorage)
  const [panelWidth, setPanelWidth] = useState<number>(() => {
    if (typeof window === 'undefined') return width;
    const saved = Number(window.localStorage.getItem(STORAGE_KEY));
    return Number.isFinite(saved) && saved >= MIN_WIDTH && saved <= MAX_WIDTH
      ? saved
      : width;
  });
  const draggingRef = useRef(false);
  const startXRef = useRef(0);
  const startWidthRef = useRef(panelWidth);

  const handleMouseDown = useCallback(
    (e: React.MouseEvent) => {
      e.preventDefault();
      draggingRef.current = true;
      startXRef.current = e.clientX;
      startWidthRef.current = panelWidth;
      document.body.style.cursor = 'col-resize';
      document.body.style.userSelect = 'none';
    },
    [panelWidth],
  );

  useEffect(() => {
    const onMove = (e: MouseEvent) => {
      if (!draggingRef.current) return;
      // dragging left increases width (panel is on the right side)
      const delta = startXRef.current - e.clientX;
      const next = Math.min(
        MAX_WIDTH,
        Math.max(MIN_WIDTH, startWidthRef.current + delta),
      );
      setPanelWidth(next);
    };
    const onUp = () => {
      if (!draggingRef.current) return;
      draggingRef.current = false;
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    };
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
    return () => {
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onUp);
    };
  }, []);

  // persist whenever width settles
  useEffect(() => {
    try {
      window.localStorage.setItem(STORAGE_KEY, String(panelWidth));
    } catch {}
  }, [panelWidth]);

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

  const isOpen = !!locationRef;
  return (
    <section
      className={cn(
        'relative flex-shrink-0 flex flex-col overflow-hidden border-l border-border',
        // Only animate when opening/closing, not while dragging
        !draggingRef.current && 'transition-[width] ease-out duration-300',
      )}
      style={{ width: isOpen ? panelWidth : 0 }}
    >
      {isOpen && (
        <>
          {/* Drag handle: 6px wide strip sitting on the left edge */}
          <div
            role="separator"
            aria-orientation="vertical"
            onMouseDown={handleMouseDown}
            className="absolute left-0 top-0 bottom-0 w-1.5 -translate-x-1/2 cursor-col-resize z-20 group"
            title="拖拽调整宽度"
          >
            <div className="h-full w-full group-hover:bg-primary/40 transition-colors" />
          </div>
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
