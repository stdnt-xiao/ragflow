import { EntityRef } from '@/components/EntityTag';
import { useGetDocumentUrl } from '@/hooks/use-document-request';
import { cn } from '@/lib/utils';
import { LucidePanelRightClose } from 'lucide-react';
import { useCallback, useMemo, useState } from 'react';
import { IHighlight } from 'react-pdf-highlighter';
import PdfPreview from '../document-preview/pdf-preview';
import { Button } from '../ui/button';

function entityRefToHighlight(
  ref: EntityRef,
  pageWidth: number,
  pageHeight: number,
): IHighlight {
  const { bbox, page_no } = ref;
  const scaledRect = {
    x1: bbox.left,
    y1: bbox.top,
    x2: bbox.right,
    y2: bbox.bottom,
    width: pageWidth,
    height: pageHeight,
    pageNumber: page_no,
  };
  return {
    id: `entity-${ref.doc_id}-${page_no}`,
    comment: { text: ref.context || ref.matched_text, emoji: '' },
    position: {
      boundingRect: scaledRect,
      rects: [scaledRect],
      pageNumber: page_no,
    },
    content: { text: ref.matched_text },
  };
}

interface EntityPdfPanelProps {
  entityRef: EntityRef | null;
  onClose: () => void;
  width?: number;
}

export function EntityPdfPanel({
  entityRef,
  onClose,
  width = 520,
}: EntityPdfPanelProps) {
  const documentId = entityRef?.doc_id ?? '';
  const getDocumentUrl = useGetDocumentUrl(documentId);
  const url = getDocumentUrl(documentId);
  const [pageSize, setPageSize] = useState({ width: 849, height: 1200 });

  // Only update pageSize when values actually change to prevent render loops.
  // pdf-preview calls setWidthAndHeight on every render (inside a render prop),
  // so we must guard against no-op updates that would re-trigger highlights recalc.
  const handleSetWidthAndHeight = useCallback((w: number, h: number) => {
    setPageSize((prev) => {
      if (prev.width === w && prev.height === h) return prev;
      return { width: w, height: h };
    });
  }, []);

  const highlights = useMemo<IHighlight[]>(
    () =>
      entityRef
        ? [entityRefToHighlight(entityRef, pageSize.width, pageSize.height)]
        : [],
    [entityRef, pageSize],
  );

  return (
    <section
      className={cn(
        'transition-[width] ease-out duration-300 flex-shrink-0 flex flex-col overflow-hidden border-l border-border',
        entityRef ? `w-[${width}px]` : 'w-0',
      )}
    >
      {entityRef && (
        <>
          <div className="p-4 pb-2 flex justify-between items-center text-sm font-medium shrink-0">
            <span className="truncate max-w-[360px]" title={entityRef.doc_name}>
              {entityRef.doc_name}
              <span className="text-text-sub-title ml-1 font-normal">
                p.{entityRef.page_no}
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

export default EntityPdfPanel;
