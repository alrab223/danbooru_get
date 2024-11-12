import asyncio
import os
import sqlite3
import traceback
from datetime import datetime

import discord
import pytz
import requests
from discord.ext import commands, tasks

from cog.util import image_download as im


class Time(commands.Cog):
   def __init__(self, bot):
      self.bot = bot
      self.db = sqlite3.connect("db/meta.db")

   def time_fetch(self, dic):
      jst = pytz.timezone("Asia/Tokyo")
      EDT = dic["created_at"]  # noqa: N806
      date_ed = datetime.strptime(EDT, "%Y-%m-%dT%H:%M:%S.%f%z")
      # JSTに変換
      date_jst = date_ed.astimezone(jst)
      date = datetime.now(jst) - date_jst
      seconds = date.total_seconds()
      return seconds

   def rate_check(self, dic, tag):
      if dic["rating"] == "g":
         channel = os.getenv(f"{tag}_GENERAL")
      elif dic["rating"] == "s":
         channel = os.getenv(f"{tag}_SENSITIVE")
      elif dic["rating"] == "q":
         channel = os.getenv(f"{tag}_QUESTIONABLE")
      else:
         channel = os.getenv(f"{tag}_EXPLICIT")
      return channel

   def info_insert(self, bulk_dic):
      cursor = self.db.cursor()
      for dic in bulk_dic:
         try:
            cursor.execute(
               f"insert into media values('{str(dic['id'])}', '{dic['file_url']}', '{dic['file_ext']}','{dic['created_at']}','{dic['rating']}')"
            )
         except KeyError:
            cursor.execute(
               f"insert into media values('{str(dic['id'])}', 'null', '{dic['file_ext']}','{dic['created_at']}','{dic['rating']}')"
            )

         sp = dic["tag_string_copyright"].split(" ")
         insert_query = "insert into copyright_tags values(?, ?)"
         cursor.executemany(insert_query, [(str(dic["id"]), i) for i in sp])

         sp = dic["tag_string_character"].split(" ")
         insert_query = "insert into character_tags values(?, ?)"
         cursor.executemany(insert_query, [(str(dic["id"]), i) for i in sp])

         sp = dic["tag_string_general"].split(" ")
         insert_query = "insert into general_tags values(?, ?)"
         cursor.executemany(insert_query, [(str(dic["id"]), i) for i in sp])

      self.db.commit()

   async def send_picture(self, dic, tag):
      bluk_dic = []
      for i in dic:
         seconds = self.time_fetch(i)
         # 投稿時間が2分以内なら送信
         if seconds > 120:
            break
         else:
            channel_id = self.rate_check(i, tag)
            channel = self.bot.get_channel(int(channel_id))
            try:
               bluk_dic.append(i)
               await channel.send(i["file_url"])
               im.download_image(
                  i["file_url"],
                  f"img/{tag}/{i['rating'].upper()}/{i['id']}.{i['file_ext']}",
               )
            except KeyError:
               print("ファイルがありません")
      self.info_insert(bluk_dic)

   async def crawler(self):
      url = "https://danbooru.donmai.us/posts.json"
      parms = {"tags": "blue_archive", "limit": 5}
      dic = requests.get(url, params=parms).json()
      await self.send_picture(dic, "BA")
      await asyncio.sleep(5)

      url = "https://danbooru.donmai.us/posts.json"
      parms = {"tags": "umamusume", "limit": 5}
      dic = requests.get(url, params=parms).json()
      await self.send_picture(dic, "UMA")

   async def copy_message(self, message, target_channel):
      content = message.content
      try:
         await target_channel.send(content)
         print(f"Copied message from {message.author.display_name} to {target_channel.name}")
      except discord.errors.Forbidden:
         print(f"Error: Bot doesn't have permission to send messages in {target_channel.name}")
      except Exception as e:
         print(f"Error copying message: {e}")

   @commands.slash_command(name="タグ検索", description="指定したタグの画像を検索します")
   async def search_tag(self, ctx, tag: str, limit: int = 5):
      cursor = self.db.cursor()
      row = cursor.execute(
         f"select media.url,general_tags.tag from general_tags inner join media on (general_tags.id=media.id) where general_tags.tag='{tag}'"
      )
      row = row.fetchall()
      if row == []:
         await ctx.respond("該当するタグが見つかりませんでした")

      for i in row:
         await ctx.respond(i[0])
         limit -= 1
         if limit == 0:
            break

   @commands.Cog.listener()
   async def on_raw_reaction_add(self, payload):
      emoji_to_watch = "😎"
      if str(payload.emoji) == emoji_to_watch:
         channel = self.bot.get_channel(payload.channel_id)
         try:
            message = await channel.fetch_message(payload.message_id)
         except discord.errors.NotFound:
            print(f"Error: Could not find message with ID {payload.message_id}")
            return

         if payload.member.id == 349052901223825408:
            target_channel = self.bot.get_channel(1267135160311087125)
         else:
            target_channel = self.bot.get_channel(1297581750532440196)

         await self.copy_message(message, target_channel)

   @tasks.loop(seconds=120)
   async def search(self):
      try:
         await self.crawler()
      except Exception as e:
         print(f"エラーが発生しましたが、ループを継続します: {e}")
         traceback.print_exc()

   @commands.Cog.listener()
   async def on_ready(self):
      print("Time Cog is Ready")
      self.search.start()


def setup(bot):
   bot.add_cog(Time(bot))
