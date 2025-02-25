import asyncio
import os
import traceback
from datetime import datetime
from typing import Any, Dict, List

import discord
import pytz
import requests
from discord.ext import commands, tasks


class Time(commands.Cog):
   def __init__(self, bot):
      self.bot = bot
      self.jst = pytz.timezone("Asia/Tokyo")
      self.post_timeout_seconds = 120  # 投稿時間の制限（秒）
      self.tag_sources = {"BA": {"tags": "blue_archive", "limit": 5}, "UMA": {"tags": "umamusume", "limit": 5}}
      self.danbooru_api_url = "https://danbooru.donmai.us/posts.json"

      # チャンネルIDのマッピング
      self.special_user_channels = {349052901223825408: 1267135160311087125, "default": 1297581750532440196}

      # 監視する絵文字
      self.reaction_emoji = "😎"

   def calculate_time_difference(self, created_at: str) -> float:
      created_datetime = datetime.strptime(created_at, "%Y-%m-%dT%H:%M:%S.%f%z")
      # JSTに変換
      created_jst = created_datetime.astimezone(self.jst)
      time_diff = datetime.now(self.jst) - created_jst
      return time_diff.total_seconds()

   def get_channel_by_rating(self, post_data: Dict[str, Any], tag: str) -> str:
      rating = post_data["rating"]
      rating_map = {"g": f"{tag}_GENERAL", "s": f"{tag}_SENSITIVE", "q": f"{tag}_QUESTIONABLE"}

      # デフォルトはEXPLICIT
      env_key = rating_map.get(rating, f"{tag}_EXPLICIT")
      return os.getenv(env_key)

   async def process_and_send_posts(self, posts: List[Dict[str, Any]], tag: str) -> None:
      processed_posts = []

      for post in posts:
         seconds_since_post = self.calculate_time_difference(post["created_at"])

         # 投稿時間が制限時間を超えたら処理を中断
         if seconds_since_post > self.post_timeout_seconds:
            break

         channel_id = self.get_channel_by_rating(post, tag)
         if not channel_id:
            print(f"チャンネルIDが見つかりません: {tag}, {post['rating']}")
            continue

         channel = self.bot.get_channel(int(channel_id))
         if not channel:
            print(f"チャンネルが見つかりません: {channel_id}")
            continue

         try:
            # 投稿を送信
            file_url = post.get("file_url")
            if not file_url:
               print("ファイルURLがありません")
               continue

            await channel.send(file_url)
            processed_posts.append(post)
         except Exception as e:
            print(f"投稿の処理中にエラーが発生: {e}")

   async def fetch_posts(self, tag_name: str, params: Dict[str, Any]) -> None:
      try:
         response = requests.get(self.danbooru_api_url, params=params)
         if response.status_code != 200:
            print(f"API呼び出しに失敗: {response.status_code}")
            return

         posts = response.json()
         await self.process_and_send_posts(posts, tag_name)
      except Exception as e:
         print(f"{tag_name}の投稿取得中にエラーが発生: {e}")

   async def crawler(self) -> None:
      for tag_name, params in self.tag_sources.items():
         await self.fetch_posts(tag_name, params)
         await asyncio.sleep(5)  # APIリクエスト間の間隔

   async def copy_message(self, message, target_channel) -> None:
      try:
         await target_channel.send(message.content)
         print(f"Copied message from {message.author.display_name} to {target_channel.name}")
      except discord.errors.Forbidden:
         print(f"Error: Bot doesn't have permission to send messages in {target_channel.name}")
      except Exception as e:
         print(f"Error copying message: {e}")

   @commands.Cog.listener()
   async def on_raw_reaction_add(self, payload) -> None:
      if str(payload.emoji) != self.reaction_emoji:
         return

      # メッセージを取得
      channel = self.bot.get_channel(payload.channel_id)
      try:
         message = await channel.fetch_message(payload.message_id)
      except discord.errors.NotFound:
         print(f"Error: Could not find message with ID {payload.message_id}")
         return

      # ターゲットチャンネルを決定
      target_channel_id = self.special_user_channels.get(payload.member.id, self.special_user_channels["default"])
      target_channel = self.bot.get_channel(target_channel_id)

      if target_channel:
         await self.copy_message(message, target_channel)

   @tasks.loop(seconds=120)
   async def search(self) -> None:
      try:
         await self.crawler()
      except Exception as e:
         print(f"エラーが発生しましたが、ループを継続します: {e}")
         traceback.print_exc()

   @commands.Cog.listener()
   async def on_ready(self) -> None:
      print("Time Cog is Ready")
      self.search.start()


def setup(bot):
   bot.add_cog(Time(bot))
