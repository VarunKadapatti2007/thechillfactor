"use client";

import dynamic from "next/dynamic";
import { DataProvider } from "@/lib/data";
import { useMediaQuery } from "@/lib/hooks";
import { StoreProvider } from "@/lib/store";
import { useUrlState } from "@/lib/urlState";
import BottomSheet from "./BottomSheet";
import Header from "./Header";
import PanelBody from "./Panel";
import { Skeleton } from "./ui";

const MapView = dynamic(() => import("./MapView"), {
  ssr: false,
  loading: () => <Skeleton className="h-full w-full rounded-none" />,
});

function Shell() {
  const desktop = useMediaQuery("(min-width: 1024px)");
  useUrlState();
  return (
    <div className="flex h-dvh flex-col overflow-hidden">
      <Header />
      <div className="relative flex min-h-0 flex-1">
        <main className="relative min-w-0 flex-1" aria-label="Map">
          <MapView />
        </main>
        {desktop ? (
          <aside aria-label="Results" className="panel-lg relative z-20 w-[60%] min-w-[540px] max-w-[980px] shrink-0 overflow-y-auto border-l border-line bg-surface shadow-[-4px_0_18px_rgba(31,42,36,0.08)]">
            <div className="mx-auto max-w-[860px] px-2">
              <PanelBody />
            </div>
          </aside>
        ) : (
          <div className="pointer-events-none absolute inset-0">
            <BottomSheet>
              <PanelBody />
            </BottomSheet>
          </div>
        )}
      </div>
    </div>
  );
}

export default function App() {
  return (
    <StoreProvider>
      <DataProvider>
        <Shell />
      </DataProvider>
    </StoreProvider>
  );
}
