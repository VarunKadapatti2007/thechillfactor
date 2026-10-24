"use client";

import dynamic from "next/dynamic";
import { DataProvider } from "@/lib/data";
import { useMediaQuery } from "@/lib/hooks";
import { StoreProvider } from "@/lib/store";
import { useUrlState } from "@/lib/urlState";
import BottomSheet from "./BottomSheet";
import { CoachMark, useCoachBoot } from "./Coach";
import Header from "./Header";
import PanelBody from "./Panel";
import SearchBox from "./SearchBox";
import { Skeleton } from "./ui";

const MapView = dynamic(() => import("./MapView"), {
  ssr: false,
  loading: () => <Skeleton className="h-full w-full rounded-none" />,
});

function Shell() {
  const desktop = useMediaQuery("(min-width: 1024px)");
  useCoachBoot();
  useUrlState();
  return (
    <div className="flex h-dvh flex-col overflow-hidden">
      <Header />
      <div className="relative flex min-h-0 flex-1">
        <main className="relative min-w-0 flex-1" aria-label="Map">
          <MapView />
          {!desktop && (
            <div className="absolute left-3 right-14 top-3 z-10">
              <SearchBox />
            </div>
          )}
          <CoachMark step={0} className="left-1/2 top-1/3 -translate-x-1/2" arrow="down" />
          {desktop && (
            <>
              <CoachMark step={1} className="right-4 top-[120px]" arrow="right" />
              <CoachMark step={2} className="right-4 top-[360px]" arrow="right" />
            </>
          )}
        </main>
        {desktop ? (
          <aside aria-label="Results" className="relative z-20 w-[440px] shrink-0 overflow-y-auto border-l border-line bg-surface shadow-[-4px_0_18px_rgba(31,42,36,0.08)]">
            <PanelBody />
          </aside>
        ) : (
          <div className="pointer-events-none absolute inset-0">
            <BottomSheet>
              <PanelBody />
            </BottomSheet>
            <CoachMark step={1} className="left-1/2 top-[calc(42%-112px)] -translate-x-1/2" arrow="down" />
            <CoachMark step={2} className="left-1/2 top-[calc(42%-112px)] -translate-x-1/2" arrow="down" />
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
