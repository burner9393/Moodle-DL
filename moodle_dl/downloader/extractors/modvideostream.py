# coding: utf-8

# mod_videostream info-extractor (for MoodleDL)
# 

from __future__ import unicode_literals

from bs4 import BeautifulSoup
import re

from yt_dlp import YoutubeDL
from yt_dlp.extractor.common import InfoExtractor
from yt_dlp.utils import ExtractorError, extract_attributes, urlencode_postdata, determine_ext

class ModVideoStreamIE(InfoExtractor):
    IE_NAME = 'modvideostream_ie'
    IE_DESC = 'mod_videostream info extractor (https://github.com/openapp1/moodle-mod_videostream)'

    _VALID_URL = r'(?P<scheme>https?://)(?P<host>[^/]+)(?P<path>.*)?/mod/videostream/view.php\?.*?id=(?P<id>\d+)'
    # _TESTS = [
    # 
    # ]

    @staticmethod
    def _match_symlink_stream(soup):
        # (videojs - default)
        # 

        source = soup.find('source', { 'type': 'video/mp4' })

        if source:
            data = {
                'source': source['src'],
                'type': 'symlink'
            }

            return data
        
        return None
    
    @staticmethod
    def _match_hls_stream(soup):
        source = soup.find('source', { 'type': 'application/x-mpegURL' })

        if source:
            data = {
                'source': source['src'],
                'type': 'hls'
            }

            return data
        
        return None

    @staticmethod
    def _match_dash_stream(soup):
        dash_manifest_url = None

        for script in soup.find_all('script'):
            if script.string and 'player.src' in script.string:
                m = re.search(r'(?P<dash_manifest_url>https?:\/\/.+?\/manifest\.mpd)', script.string)
                if m:
                    dash_manifest_url = m.group('dash_manifest_url')
                    break
                
        if not dash_manifest_url:
            return
        
        data = {
            'source': dash_manifest_url,
            'type': 'dash'
        }

        return data

    @staticmethod
    def _match_vimeo_stream(soup):
        div = soup.find('div', attrs={ 'data-vimeo-id': True })

        data = {
            'video_id': div.get('videoid'),
            'vimeo_id': div.get('data-vimeo-id'),
            'width': div.get('data-vimeo-width'),
            'height': div.get('data-vimeo-height'),
            'responsive': div.get('data-vimeo-responsive'),
            'controls': div.get('data-vimeo-controls'),
        }

        # add source for yt-dlp:
        # 

        vimeo_id = data['vimeo_id']
        data['source'] = f'https://vimeo.com/{vimeo_id}'

        return data

    def _get_stream_match_handlers(self):
        return {
            'symlink': self._match_symlink_stream,
            'hls': self._match_hls_stream,
            'vimeo': self._match_vimeo_stream,
            'dash': self._match_dash_stream
        }
        
    def _match_video_stream(self, page_data):
        matched_stream = None

        soup = BeautifulSoup(page_data, 'html.parser')
        handlers = self._get_stream_match_handlers()

        # TODO: inline videos?
        # 

        for name, handler in handlers.items():
            matched_stream = handler(soup)
            if matched_stream:
                if 'type' not in matched_stream:
                    matched_stream['type'] = name
                break
        
        if not matched_stream:
            raise RuntimeError('failed finding stream')
        
        return matched_stream

    def _real_extract(self, url):
        # parse title as video name / get metadata
        # 

        video_id = self._match_id(url)
        webpage = self._download_webpage(url, video_id)

        try:
            stream = self._match_video_stream(webpage)
        except Exception as e:
            raise ExtractorError(f'failed finding stream: {e}', expected=True)

        stream_type = stream['type']
        source_url = stream['source']

        title = self._html_search_regex(
            [ r'<h1 class="h2[^"]+">([^<]+)', r'<title>([^|<]+)' ],
            webpage, 'title', default='videostream_anonymous'
        ).strip()

        self.to_screen(f'title: {title}')

        if stream_type == 'vimeo':
            return self.url_result(source_url, 'Vimeo', video_id)

        formats = [ ]
        if stream_type == 'symlink':
            formats.append({
                'url': source_url,
                'format_id': 'direct',
                'ext': determine_ext(source_url, default_ext='mp4')
            })
        elif stream_type == 'hls':
            formats = self._extract_m3u8_formats(
                source_url, video_id, 'mp4',
                entry_protocol='m3u8_native', m3u8_id='hls'
            )
        elif stream_type == 'dash':
            formats = self._extract_mpd_formats(
                source_url, video_id, mpd_id='dash'
            )
        else:
            raise ExtractorError(f'invalid stream type: \'{stream_type}\' (no format handler)')

        #self._sort_formats(formats)

        return {
            'id': video_id,
            'title': title,
            'formats': formats
        }
    
