# typed: true
# frozen_string_literal: true

require File.expand_path("../Abstract/abstract-php-extension", __dir__)

# Class for Protobuf Extension
class ProtobufAT82 < AbstractPhpExtension
  init
  desc "Protobuf PHP extension"
  homepage "https://github.com/protocolbuffers/protobuf"
  url "https://pecl.php.net/get/protobuf-4.27.3.tgz"
  sha256 "7c709680073db7fffaf95bf6b66c374cdfd0bce05a869dfbb22bf89c8492d9e5"
  head "https://github.com/protocolbuffers/protobuf.git"
  license "BSD-3-Clause"

  bottle do
    root_url "https://ghcr.io/v2/shivammathur/extensions"
    sha256 cellar: :any_skip_relocation, arm64_sonoma:   "3eed3a6c37c755593b7ff64e79744bd33e88981d0ed77da8aadfb6f600bb064a"
    sha256 cellar: :any_skip_relocation, arm64_ventura:  "328331a72d19ff4b90dd9a5d8f3b25456a5c75e80c2c777931ba75c4c96f8718"
    sha256 cellar: :any_skip_relocation, arm64_monterey: "7ffd5fdd9955a75e9f91799689c6f303781edd253d5c18ff410a36fdd35c6ba5"
    sha256 cellar: :any_skip_relocation, ventura:        "85cb9e05fcc79204794368757619142dcb6d5e84f5b76fbfc78047756fdbcf0e"
    sha256 cellar: :any_skip_relocation, monterey:       "6491ed8297a0f8177e46e40e8651110840fe78a4f58f5e56933a17a69e716991"
    sha256 cellar: :any_skip_relocation, x86_64_linux:   "6021f3e6f5d556b828fec32ceb66657f18b238389cfb00c164f804991cfcaa13"
  end

  def install
    Dir.chdir "protobuf-#{version}"
    patch_spl_symbols
    safe_phpize
    system "./configure", "--enable-protobuf"
    system "make"
    prefix.install "modules/#{extension}.so"
    write_config_file
  end

  def caveats
    <<~EOS
      Copyright 2008 Google Inc.  All rights reserved.

      Redistribution and use in source and binary forms, with or without
      modification, are permitted provided that the following conditions are
      met:

          * Redistributions of source code must retain the above copyright
      notice, this list of conditions and the following disclaimer.
          * Redistributions in binary form must reproduce the above
      copyright notice, this list of conditions and the following disclaimer
      in the documentation and/or other materials provided with the
      distribution.
          * Neither the name of Google Inc. nor the names of its
      contributors may be used to endorse or promote products derived from
      this software without specific prior written permission.

      THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
      "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
      LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
      A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
      OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
      SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
      LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
      DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
      THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
      (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
      OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

      Code generated by the Protocol Buffer compiler is owned by the owner
      of the input file used when generating it.  This code is not
      standalone and requires a support library to be linked with it.  This
      support library is itself covered by the above license.

      To finish installing #{extension} for PHP #{php_version}:
        * #{config_filepath} was created,"
          do not forget to remove it upon extension removal."
        * Validate installation by running php -m
    EOS
  end
end
