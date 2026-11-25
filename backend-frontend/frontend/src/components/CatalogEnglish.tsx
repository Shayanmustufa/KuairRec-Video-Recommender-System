'use client';

import { createContext, useContext, type ReactNode } from 'react';
import type { CatalogTranslations } from '@/lib/format';

const CatalogEnglish = createContext<CatalogTranslations>({});

export function CatalogEnglishProvider({ translations, children }: { translations: CatalogTranslations; children: ReactNode }) {
  return <CatalogEnglish.Provider value={translations}>{children}</CatalogEnglish.Provider>;
}

export function useCatalogEnglish() {
  return useContext(CatalogEnglish);
}
