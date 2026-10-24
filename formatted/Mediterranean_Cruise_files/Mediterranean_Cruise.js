// Created by iWeb 3.0.4 local-build-20130428

function createMediaStream_id3() {
  return IWCreatePhotocast("Mediterranean_Cruise_files/rss.xml", true);
}
function initializeMediaStream_id3() {
  createMediaStream_id3().load("", function(imageStream) {
    var entryCount = imageStream.length;
    var headerView = widgets["widget1"];
    headerView.setPreferenceForKey(imageStream.length, "entryCount");
    NotificationCenter.postNotification(new IWNotification("SetPage", "id3", { pageIndex: 0 }));
  });
}
function layoutMediaGrid_id3(range) {
  createMediaStream_id3().load("", function(imageStream) {
    if (range == null) {
      range = new IWRange(0, imageStream.length);
    }
    IWLayoutPhotoGrid("id3", new IWPhotoGridLayout(4, new IWSize(141, 141), new IWSize(141, 28), new IWSize(154, 184), 27, 27, 0, new IWSize(18, 18)), new IWPhotoFrame([IWCreateImage("Mediterranean_Cruise_files/Watercolor_iweb_01.png"), IWCreateImage("Mediterranean_Cruise_files/Watercolor_iweb_02.png"), IWCreateImage("Mediterranean_Cruise_files/Watercolor_iweb_04.png"), IWCreateImage("Mediterranean_Cruise_files/Watercolor_iweb_08.png"), IWCreateImage("Mediterranean_Cruise_files/Watercolor_iweb_16.png"), IWCreateImage("Mediterranean_Cruise_files/Watercolor_iweb_14.png"), IWCreateImage("Mediterranean_Cruise_files/Watercolor_iweb_13.png"), IWCreateImage("Mediterranean_Cruise_files/Watercolor_iweb_05.png")], null, 0, 0.75, 0, 0, 0, 0, 12, 12, 11, 11, 13, 12, 13, 12, null, null, null, 0.5), imageStream, range, null, null, 1, { backgroundColor: "rgb(0, 0, 0)", reflectionHeight: 0, reflectionOffset: 2, captionHeight: 100, fullScreen: 1, transitionIndex: 2 }, "Media/slideshow.html", "widget1", "widget2", "widget3");
  });
}
function relayoutMediaGrid_id3(notification) {
  var userInfo = notification.userInfo();
  var range = userInfo["range"];
  layoutMediaGrid_id3(range);
}
function onStubPage() {
  var args = window.location.href.toQueryParams();
  parent.IWMediaStreamPhotoPageSetMediaStream(createMediaStream_id3(), args.id);
}
if (window.stubPage) {
  onStubPage();
}
setTransparentGifURL("Media/transparent.gif");
function hostedOnDM() {
  return false;
}
function onPageLoad() {
  IWRegisterNamedImage("comment overlay", "Media/Photo-Overlay-Comment.png");
  IWRegisterNamedImage("movie overlay", "Media/Photo-Overlay-Movie.png");
  loadMozillaCSS("Mediterranean_Cruise_files/Mediterranean_CruiseMoz.css");
  adjustLineHeightIfTooBig("id1");
  adjustFontSizeIfTooBig("id1");
  adjustLineHeightIfTooBig("id2");
  adjustFontSizeIfTooBig("id2");
  NotificationCenter.addObserver(null, relayoutMediaGrid_id3, "RangeChanged", "id3");
  adjustLineHeightIfTooBig("id4");
  adjustFontSizeIfTooBig("id4");
  Widget.onload();
  initializeMediaStream_id3();
  performPostEffectsFixups();
}
function onPageUnload() {
  Widget.onunload();
}
