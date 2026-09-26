'use client';

/**
 * 영상 설정 모음 — 자막 / 음성 / 말하는 속도 / 배경음악 (2026-09-27).
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

type Props = {
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

  disabled?: boolean;
};

export default function SettingsPanel({
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

  return (
    <Box sx={{ width: '100%' }}>
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
