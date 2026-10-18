'use client';

/**
 * 영상 설정 모음 — 화면 배치 / 자막 / 음성 / 말하는 속도 / 화면 효과 / 배경음악 (2026-09-27, 효과 2026-10-18).
 *
 * ## 왜 모았나
 * 설정이 늘어나는 동안 자리를 그때그때 잡았다. 자막 스타일만 접히는 카드로 위에
 * 있었고, 음성·속도·배경음악은 스크립트 패널 안에 펼쳐진 채로 쌓였다. 2페이지에
 * 들어오면 설정 네 덩어리를 지나야 스크립트가 보였고, 배경음악이 붙으면서
 * 20곡짜리 목록까지 늘 펼쳐져 있었다.
 *
 * 넷을 한 자리에 모으고 전부 접는다. 기본은 접힌 상태다 — 대부분의 유저는
 * 설정을 건드리지 않고 이미지만 고른다.
 *
 * ## 헤더에 현재 값을 띄운다
 * 접힌 카드가 아무 정보도 안 주면 "내가 뭘 골랐는지" 확인하려고 매번 열어야 한다.
 * 특히 배경음악은 **기본 음악 / 음악 없음 / 고른 곡**이 전부 다른 결과라, 헤더에서
 * 구분되지 않으면 곡을 고른 줄 알고 넘어가게 된다.
 *
 * ## PC·모바일 같은 것을 쓴다
 * 전에는 자막 스타일이 PC 분기에만 있어서 모바일에서는 아예 없는 기능이었다.
 * 유저 대부분이 모바일이라(기존 VoicePicker 주석) 한쪽에만 두면 없는 것과 같다.
 */
import * as React from 'react';
import { Box } from '@mui/material';

import CollapsibleSection, { SummaryChip } from './CollapsibleSection';
import SubtitleStyleEditor, { SubtitleSettings } from './SubtitleStyleEditor';
import VoicePicker, { Voice } from './VoicePicker';
import SpeedPicker, { Speed } from './SpeedPicker';
import MusicPicker, { MusicTrack, MusicConcept, BGM_TEMPLATE_DEFAULT } from './MusicPicker';
import EffectPicker, { EffectOption } from './EffectPicker';
import BookendPicker, { BookendOption } from './BookendPicker';
import LayoutPicker, { LayoutOption, PlaceInfo } from './LayoutPicker';

type Props = {
  /** 화면 배치 */
  layouts: LayoutOption[];
  layout: string;
  onSelectLayout: (id: string) => void;
  place: PlaceInfo;
  onPlaceChange: (p: PlaceInfo) => void;
  onFetchPlace: () => void;
  placeLoading: boolean;

  /** 자막 */
  onSubtitleSettingsChange: (s: SubtitleSettings) => void;

  /** 음성 */
  voices: Voice[];
  voiceId: string;
  onSelectVoice: (id: string) => void;
  previewText: string;
  previewBlockedReason: string | null;
  apiBaseUrl: string;
  authHeaders: () => Record<string, string>;

  /** 말하는 속도 */
  speeds: Speed[];
  speed: number;
  onSelectSpeed: (v: number) => void;

  /** 배경음악 */
  musicConcepts: MusicConcept[];
  musicTracks: MusicTrack[];
  musicNoneId: string;
  bgmId: string;
  onSelectBgm: (id: string) => void;
  onMusicExpired: () => Promise<MusicTrack[] | null>;

  /** 화면 효과 */
  motions: EffectOption[];
  transitions: EffectOption[];
  sounds: EffectOption[];
  motion: string;
  transition: string;
  sound: string;
  onSelectMotion: (id: string) => void;
  onSelectTransition: (id: string) => void;
  onSelectSound: (id: string) => void;

  /** 첫 화면 문구 · 끝 화면 */
  intros: BookendOption[];
  outros: BookendOption[];
  intro: string;
  introText: string;
  outro: string;
  outroText: string;
  bookendMaxText: number;
  onIntro: (id: string) => void;
  onIntroText: (t: string) => void;
  onOutro: (id: string) => void;
  onOutroText: (t: string) => void;

  disabled?: boolean;
};

export default function SettingsPanel({
  layouts,
  layout,
  onSelectLayout,
  place,
  onPlaceChange,
  onFetchPlace,
  placeLoading,
  onSubtitleSettingsChange,
  voices,
  voiceId,
  onSelectVoice,
  previewText,
  previewBlockedReason,
  apiBaseUrl,
  authHeaders,
  speeds,
  speed,
  onSelectSpeed,
  musicConcepts,
  musicTracks,
  musicNoneId,
  bgmId,
  onSelectBgm,
  onMusicExpired,
  motions,
  transitions,
  sounds,
  motion,
  transition,
  sound,
  onSelectMotion,
  onSelectTransition,
  onSelectSound,
  intros,
  outros,
  intro,
  introText,
  outro,
  outroText,
  bookendMaxText,
  onIntro,
  onIntroText,
  onOutro,
  onOutroText,
  disabled = false,
}: Props) {
  const voiceName = voices.find(v => v.voice_id === voiceId)?.name ?? '기본';
  const speedName = speeds.find(s => Math.abs(s.value - speed) < 1e-6)?.name ?? '1배';

  // 배경음악은 세 가지가 서로 다른 결과다 — 헤더에서 반드시 구분돼야 한다.
  const bgmName =
    bgmId === BGM_TEMPLATE_DEFAULT
      ? '기본 음악'
      : bgmId === musicNoneId
        ? '음악 없음'
        : (musicTracks.find(t => t.id === bgmId)?.title ?? '기본 음악');

  // 화면 효과 요약. 둘 다 "없음"이면 한 칩으로 — "없음 · 없음"은 읽기 어색하다.
  const motionName = motions.find(m => m.id === motion)?.name ?? '없음';
  const transitionName = transitions.find(t => t.id === transition)?.name ?? '없음';
  const soundName = sounds.find(o => o.id === sound)?.name ?? '없음';
  const effectChips =
    motion === 'none' && transition === 'none' && sound === 'none'
      ? ['효과 없음']
      : [
          motion === 'none' ? '사진 고정' : motionName,
          transition === 'none' ? '바로 전환' : `전환 ${transitionName}`,
          ...(sound === 'none' ? [] : [`소리 ${soundName}`]),
        ];

  // 첫 화면·끝 화면 요약. "직접 입력"인데 비어 있으면 실제로 아무것도 안 붙으니 "없음"으로 보여준다.
  const bookendChip = (opts: BookendOption[], id: string, text: string, prefix: string) => {
    if (id === 'none' || (id === 'custom' && !text.trim())) return null;
    return `${prefix} ${opts.find(o => o.id === id)?.name ?? ''}`.trim();
  };
  const bookendChips = [
    bookendChip(intros, intro, introText, '첫'),
    bookendChip(outros, outro, outroText, '끝'),
  ].filter((x): x is string => !!x);

  return (
    <Box sx={{ width: '100%' }}>
      {/* 화면 배치 — 영상의 생김새를 가장 크게 바꾸는 선택이라 맨 위 (백로그 2-1) */}
      {layouts.length > 1 && (
        <CollapsibleSection
          title="화면 배치"
          badge="선택 사항"
          summary={<SummaryChip text={layouts.find(l => l.id === layout)?.name ?? '기본'} />}
        >
          <LayoutPicker
            layouts={layouts}
            selected={layout}
            onSelect={onSelectLayout}
            place={place}
            onPlaceChange={onPlaceChange}
            onFetchPlace={onFetchPlace}
            placeLoading={placeLoading}
            placeMax={30}
            disabled={disabled}
          />
        </CollapsibleSection>
      )}

      {/* 자막 — 이 카드는 자체 접힘 UI 를 갖고 있다 (헤더 모양이 같아 나란히 쌓인다) */}
      <SubtitleStyleEditor onSettingsChange={onSubtitleSettingsChange} />

      {/* 음성 — 목록을 못 받으면 통째로 숨긴다. BE 가 기본값(혜리)으로 흐르므로
          UI 가 없다고 영상 생성이 막히지는 않는다. */}
      {voices.length > 0 && (
        <CollapsibleSection
          title="음성"
          badge="선택 사항"
          summary={
            <>
              <SummaryChip text={voiceName} />
              {/* 미리듣기가 이 속도로 나간다 — 속도 카드가 접혀 있어도 보이게 둔다 */}
              <SummaryChip text={speedName} />
            </>
          }
        >
          <VoicePicker
            voices={voices}
            selected={voiceId}
            onSelect={onSelectVoice}
            selectedSpeed={speed}
            previewText={previewText}
            disabled={disabled}
            previewBlockedReason={previewBlockedReason}
            apiBaseUrl={apiBaseUrl}
            authHeaders={authHeaders}
          />
        </CollapsibleSection>
      )}

      {/* 말하는 속도 */}
      {speeds.length > 0 && (
        <CollapsibleSection
          title="말하는 속도"
          badge="선택 사항"
          summary={<SummaryChip text={speedName} />}
        >
          <SpeedPicker
            speeds={speeds}
            selected={speed}
            onSelect={onSelectSpeed}
            disabled={disabled}
          />
        </CollapsibleSection>
      )}

      {/* 화면 효과 — 사진 움직임 · 장면 전환 (백로그 3-7) */}
      {(motions.length > 0 || transitions.length > 0 || sounds.length > 0) && (
        <CollapsibleSection
          title="화면 효과"
          badge="선택 사항"
          summary={<>{effectChips.map(t => <SummaryChip key={t} text={t} />)}</>}
        >
          <EffectPicker
            motions={motions}
            transitions={transitions}
            sounds={sounds}
            motion={motion}
            transition={transition}
            sound={sound}
            onSelectMotion={onSelectMotion}
            onSelectTransition={onSelectTransition}
            onSelectSound={onSelectSound}
            disabled={disabled}
          />
        </CollapsibleSection>
      )}

      {/* 첫 화면 문구 · 끝 화면 (백로그 3-6) */}
      {(intros.length > 0 || outros.length > 0) && (
        <CollapsibleSection
          title="첫 화면 · 끝 화면"
          badge="선택 사항"
          summary={
            <>
              {(bookendChips.length ? bookendChips : ['없음']).map(t => (
                <SummaryChip key={t} text={t} />
              ))}
            </>
          }
        >
          <BookendPicker
            intros={intros}
            outros={outros}
            intro={intro}
            introText={introText}
            outro={outro}
            outroText={outroText}
            maxText={bookendMaxText}
            onIntro={onIntro}
            onIntroText={onIntroText}
            onOutro={onOutro}
            onOutroText={onOutroText}
            disabled={disabled}
          />
        </CollapsibleSection>
      )}

      {/* 배경음악 */}
      {musicTracks.length > 0 && (
        <CollapsibleSection
          title="배경음악"
          badge="선택 사항"
          summary={<SummaryChip text={bgmName} />}
        >
          <MusicPicker
            concepts={musicConcepts}
            tracks={musicTracks}
            noneId={musicNoneId}
            selected={bgmId}
            onSelect={onSelectBgm}
            onExpired={onMusicExpired}
            disabled={disabled}
          />
        </CollapsibleSection>
      )}
    </Box>
  );
}
